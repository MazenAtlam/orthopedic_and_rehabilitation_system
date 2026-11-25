"""Clinical record persistence helper used by the FHIR Encounter writer."""

from typing import Any

from sqlalchemy import select

from app.auth.permissions import current_actor
from app.models import Icd10Code, MedicalRecord, Patient, Staff
from app.utils.common import ApiError, as_date, as_int, as_text


def clinician_id(session: Any) -> int:
    actor = current_actor()
    identity = session.scalar(
        select(Staff.staff_id).where(Staff.user_id == actor.user_id)
    )
    if identity is None:
        raise ApiError(403, "forbidden", "A linked practitioner profile is required.")
    return int(identity)


def insert_visit(session: Any, data: dict[str, Any]) -> MedicalRecord:
    patient_id = as_int(data.get("patient_id"), "patient_id")
    visit = as_date(data.get("visit_date"), "visit_date")
    code = as_text(data.get("icd10_code"), "icd10_code", maximum=10).upper()
    practitioner = clinician_id(session)
    if "staff_id" in data and as_int(data["staff_id"], "staff_id") != practitioner:
        raise ApiError(
            403, "forbidden", "The practitioner must match the signed-in account."
        )

    if (
        session.scalar(
            select(Patient.patient_id).where(Patient.patient_id == patient_id)
        )
        is None
    ):
        raise ApiError(404, "not-found", "Patient not found.")
    if session.scalar(select(Icd10Code.code).where(Icd10Code.code == code)) is None:
        raise ApiError(422, "code-invalid", "Choose an ICD-10 code from the catalogue.")

    record = MedicalRecord(
        patient_id=patient_id,
        staff_id=practitioner,
        visit_date=visit,
        icd10_code=code,
        chief_complaint=as_text(
            data.get("chief_complaint"), "chief_complaint", maximum=4000, optional=True
        ),
        affected_area=as_text(
            data.get("affected_area"), "affected_area", maximum=100, optional=True
        ),
        diagnosis=as_text(
            data.get("diagnosis"), "diagnosis", maximum=4000, optional=True
        ),
        notes=as_text(data.get("notes"), "notes", maximum=4000, optional=True),
    )
    session.add(record)
    session.flush()
    return record
