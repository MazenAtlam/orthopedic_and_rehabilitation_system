"""Create FHIR resources represented by staff workflows using the ORM models."""

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import Range

from app.fhir.resources import APPOINTMENT_TYPES, ICD10_SYSTEM, REHAB_METRICS
from app.models import (
    Appointment,
    AppointmentStatus,
    AppointmentType,
    MedicalRecord,
    Patient,
    Prescription,
    RehabSession,
    Staff,
    TreatmentPlan,
    TreatmentPlanStatus,
)
from app.services.records import clinician_id, insert_visit
from app.utils.common import ApiError, as_date, as_int, as_money, as_text

CARE_PLAN_STATUS = {
    "active": TreatmentPlanStatus.active,
    "completed": TreatmentPlanStatus.completed,
    "revoked": TreatmentPlanStatus.stopped,
}


def field(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ApiError(422, "value", f"Provide {key} as an object.")
    return value


def only(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise ApiError(422, "value", f"Provide exactly one {key} entry.")
    return value[0]


def reference(value: Any, kind: str) -> int:
    target = value.get("reference") if isinstance(value, dict) else None
    match = (
        re.fullmatch(rf"{kind}/([0-9]{{1,10}})", target)
        if isinstance(target, str)
        else None
    )
    if match is None:
        raise ApiError(422, "value", f"Provide a relative {kind} reference.")
    return as_int(match[1], f"{kind} reference")


def require_subject(data: dict[str, Any], expected: Any) -> None:
    if reference(data.get("subject"), "Patient") != expected:
        raise ApiError(
            422, "value", "The subject must match the related record's patient."
        )


def instant(value: Any, key: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value
    ):
        raise ApiError(
            422, "value", f"{key} must be a FHIR instant with seconds and timezone."
        )
    try:
        time = datetime.fromisoformat(value).astimezone(timezone.utc)
        if not 1900 <= time.year <= 2200:
            raise ValueError
        return time
    except (ValueError, OverflowError):
        raise ApiError(422, "value", f"{key} must be a valid FHIR instant.") from None


def appointment_participants(data: dict[str, Any]) -> dict[str, int]:
    participants = data.get("participant")
    message = "Provide one accepted Patient and one accepted Practitioner participant."
    if not isinstance(participants, list) or len(participants) != 2:
        raise ApiError(422, "value", message)
    actors: dict[str, int] = {}
    for participant in participants:
        if not isinstance(participant, dict) or participant.get("status") != "accepted":
            raise ApiError(422, "value", message)
        actor = participant.get("actor")
        ref = actor.get("reference") if isinstance(actor, dict) else None
        kind = ref.split("/", 1)[0] if isinstance(ref, str) else None
        if kind not in ("Patient", "Practitioner") or kind in actors:
            raise ApiError(422, "value", message)
        actors[kind] = reference(actor, kind)
    return actors


def appointment_slot(start: datetime, end: datetime) -> Range[datetime]:
    if end <= start:
        raise ApiError(422, "value", "Appointment end must be after start.")
    return Range(start, end, bounds="[)")


def create_appointment(session: Any, data: dict[str, Any]) -> int:
    if data.get("status") != "booked":
        raise ApiError(422, "value", "Provide a booked FHIR Appointment resource.")
    start = instant(data.get("start"), "start")
    end = instant(data.get("end"), "end")
    slot = appointment_slot(start, end)
    actors = appointment_participants(data)
    selected = data.get("appointmentType", {"text": "consultation"})
    if not isinstance(selected, dict) or selected.get("text") not in APPOINTMENT_TYPES:
        raise ApiError(
            422, "value", "Choose a consultation, therapy or imaging appointment type."
        )
    if session.get(Patient, actors["Patient"]) is None:
        raise ApiError(422, "not-found", "The referenced Patient is unavailable.")
    if session.get(Staff, actors["Practitioner"]) is None:
        raise ApiError(422, "not-found", "The referenced Practitioner is unavailable.")

    assert slot.lower is not None and slot.upper is not None
    overlap = session.scalar(
        select(Appointment.appointment_id)
        .where(
            Appointment.staff_id == actors["Practitioner"],
            Appointment.status == AppointmentStatus.booked,
            Appointment.start_time < slot.upper,
            Appointment.end_time > slot.lower,
        )
        .limit(1)
    )
    if overlap is not None:
        raise ApiError(
            409, "conflict", "The practitioner already has a booking in this period."
        )

    record = Appointment(
        patient_id=actors["Patient"],
        staff_id=actors["Practitioner"],
        type=AppointmentType(selected["text"]),
        start_time=slot.lower,
        end_time=slot.upper,
        status=AppointmentStatus.booked,
        notes=as_text(data.get("comment"), "comment", maximum=4000, optional=True),
    )
    session.add(record)
    session.flush()
    return record.appointment_id


def create_encounter(session: Any, data: dict[str, Any]) -> int:
    if data.get("status") != "finished" or field(data, "class").get("code") != "AMB":
        raise ApiError(422, "value", "Provide a finished ambulatory Encounter.")
    person = reference(data.get("subject"), "Patient")
    condition = only(data, "contained")
    diagnosis_ref = field(only(data, "diagnosis"), "condition").get("reference")
    condition_id = condition.get("id")
    if (
        condition.get("resourceType") != "Condition"
        or not isinstance(condition_id, str)
        or not re.fullmatch(r"[A-Za-z0-9.-]{1,64}", condition_id)
        or diagnosis_ref != f"#{condition_id}"
    ):
        raise ApiError(
            422,
            "value",
            "Reference one contained Condition as the encounter diagnosis.",
        )
    require_subject(condition, person)
    concept = field(condition, "code")
    coding = only(concept, "coding")
    if coding.get("system") != ICD10_SYSTEM:
        raise ApiError(422, "code-invalid", "Supply the HL7 ICD-10 coding system.")

    values: dict[str, Any] = {
        "patient_id": person,
        "visit_date": field(data, "period").get("start"),
        "icd10_code": coding.get("code"),
        "diagnosis": concept.get("text"),
    }
    if "participant" in data:
        values["staff_id"] = reference(
            only(data, "participant").get("individual"), "Practitioner"
        )
    if "reasonCode" in data:
        values["chief_complaint"] = only(data, "reasonCode").get("text")
    return insert_visit(session, values).record_id


def create_medication_request(session: Any, data: dict[str, Any]) -> int:
    if data.get("status") != "unknown" or data.get("intent") != "order":
        raise ApiError(
            422,
            "value",
            "Provide an order with unknown status for the prescription record.",
        )
    record_id = reference(data.get("encounter"), "Encounter")
    owner = session.scalar(
        select(MedicalRecord.patient_id).where(MedicalRecord.record_id == record_id)
    )
    if owner is None:
        raise ApiError(422, "not-found", "The referenced Encounter is unavailable.")
    require_subject(data, owner)
    medication = as_text(
        field(data, "medicationCodeableConcept").get("text"), "medication", maximum=150
    )
    instructions = None
    if "dosageInstruction" in data:
        instructions = as_text(
            only(data, "dosageInstruction").get("text"),
            "dosageInstruction",
            maximum=4000,
        )
    rx = Prescription(
        record_id=record_id,
        medication=medication,
        instructions=instructions,
    )
    session.add(rx)
    session.flush()
    return rx.prescription_id


def create_care_plan(session: Any, data: dict[str, Any]) -> int:
    status = data.get("status")
    if (
        not isinstance(status, str)
        or status not in CARE_PLAN_STATUS
        or data.get("intent") != "plan"
    ):
        raise ApiError(
            422,
            "value",
            "Provide an active, completed or revoked CarePlan with intent plan.",
        )
    owner = reference(data.get("subject"), "Patient")
    if session.get(Patient, owner) is None:
        raise ApiError(422, "not-found", "The referenced Patient is unavailable.")
    practitioner = clinician_id(session)
    if "author" in data and reference(data["author"], "Practitioner") != practitioner:
        raise ApiError(
            403, "forbidden", "The CarePlan author must match the signed-in account."
        )
    period = field(data, "period")
    start = as_date(period.get("start"), "period.start")
    end = as_date(period["end"], "period.end") if "end" in period else None
    if end is not None and end < start:
        raise ApiError(
            422, "value", "The CarePlan end date must be on or after its start."
        )
    plan = TreatmentPlan(
        patient_id=owner,
        staff_id=practitioner,
        status=CARE_PLAN_STATUS[status],
        title=as_text(data.get("title"), "title", maximum=150),
        goal=as_text(
            data.get("description"), "description", maximum=4000, optional=True
        ),
        start_date=start,
        end_date=end,
    )
    session.add(plan)
    session.flush()
    return plan.plan_id


def create_procedure(session: Any, data: dict[str, Any]) -> int:
    if (
        data.get("status") != "completed"
        or field(data, "code").get("text") != "Rehabilitation session"
    ):
        raise ApiError(
            422, "value", "Provide a completed rehabilitation session Procedure."
        )
    plan_id = reference(only(data, "basedOn"), "CarePlan")
    owner = session.scalar(
        select(TreatmentPlan.patient_id).where(TreatmentPlan.plan_id == plan_id)
    )
    if owner is None:
        raise ApiError(422, "not-found", "The referenced CarePlan is unavailable.")
    require_subject(data, owner)
    notes = (
        as_text(only(data, "note").get("text"), "note", maximum=4000)
        if "note" in data
        else None
    )
    rehab = RehabSession(
        plan_id=plan_id,
        session_date=as_date(data.get("performedDateTime"), "performedDateTime"),
        notes=notes,
    )
    session.add(rehab)
    session.flush()
    return rehab.session_id


def create_observation(session: Any, data: dict[str, Any]) -> str:
    label = field(data, "code").get("text")
    if data.get("status") != "final" or label not in REHAB_METRICS.values():
        raise ApiError(
            422, "value", "Provide a final pain score or range-of-motion Observation."
        )
    session_id = reference(only(data, "partOf"), "Procedure")
    rehab = (
        session.execute(
            select(
                TreatmentPlan.patient_id,
                RehabSession.session_date,
            )
            .select_from(RehabSession)
            .join(TreatmentPlan, RehabSession.plan_id == TreatmentPlan.plan_id)
            .where(RehabSession.session_id == session_id)
        )
        .mappings()
        .one_or_none()
    )
    if rehab is None:
        raise ApiError(422, "not-found", "The referenced Procedure is unavailable.")
    require_subject(data, rehab["patient_id"])
    if "effectiveDateTime" in data:
        effective = as_date(data["effectiveDateTime"], "effectiveDateTime")
        if effective != rehab["session_date"]:
            raise ApiError(
                422,
                "value",
                "The observation date must match the rehabilitation session.",
            )

    quantity = field(data, "valueQuantity")
    value = quantity.get("value")
    column: Any
    field_name: str
    if label == REHAB_METRICS["pain"]:
        if (
            type(value) is not int
            or not 0 <= value <= 10
            or quantity.get("unit", "score") != "score"
        ):
            raise ApiError(
                422, "value", "Pain score must be a whole number from 0 to 10."
            )
        metric, column, field_name = "pain", RehabSession.pain_score, "pain_score"
    else:
        value = as_money(value, "valueQuantity.value")
        if (
            value > Decimal("9999.99")
            or quantity.get("unit", "degrees") != "degrees"
            or ("code" in quantity and quantity["code"] != "deg")
        ):
            raise ApiError(
                422, "value", "Range of motion must be in degrees, from 0 to 9999.99."
            )
        metric, column, field_name = (
            "rom",
            RehabSession.range_of_motion,
            "range_of_motion",
        )
    updated = session.execute(
        update(RehabSession)
        .where(RehabSession.session_id == session_id, column.is_(None))
        .values({field_name: value})
    )
    if updated.rowcount == 0:
        raise ApiError(
            409, "duplicate", "This measurement was already recorded for the session."
        )
    session.flush()
    return f"{session_id}-{metric}"


WRITERS = {
    "Appointment": create_appointment,
    "Encounter": create_encounter,
    "MedicationRequest": create_medication_request,
    "CarePlan": create_care_plan,
    "Procedure": create_procedure,
    "Observation": create_observation,
}
