"""FHIR R4 resource mappings backed by the ORM models."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import String, cast, literal, select, union_all

from app.models import (
    Appointment,
    CdssResult,
    Icd10Code,
    Invoice,
    InvoiceItem,
    MedicalRecord,
    Patient,
    Payment,
    PaymentStatus,
    Prescription,
    RehabSession,
    Scan,
    Service,
    Staff,
    TreatmentPlan,
)

ICD10_SYSTEM = "http://hl7.org/fhir/sid/icd-10"
APPOINTMENT_STATUS = {
    "booked": "booked",
    "completed": "fulfilled",
    "cancelled": "cancelled",
    "no_show": "noshow",
}
APPOINTMENT_TYPES = ("consultation", "therapy", "imaging")
REHAB_METRICS = {"pain": "Pain score (0 to 10)", "rom": "Range of motion"}
REPORT_STATUS = {
    "pending": "preliminary",
    "accepted": "final",
    "rejected": "entered-in-error",
}


def ref(kind: str, identity: Any) -> dict[str, str]:
    return {"reference": f"{kind}/{identity}"}


def r4_text(value: Any) -> dict[str, Any]:
    return {"text": value}


def patient_resource(row: Any, _session: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": [r4_text(row["full_name"])],
        "birthDate": row["birth_date"],
        "gender": row["gender"],
    }
    if row["phone"]:
        result["telecom"] = [{"system": "phone", "value": row["phone"]}]
    if row["address"]:
        result["address"] = [r4_text(row["address"])]
    return result


def practitioner_resource(row: Any, _session: Any) -> dict[str, Any]:
    return {"name": [r4_text(row["full_name"])]}


def appointment_resource(row: Any, _session: Any) -> dict[str, Any]:
    status = APPOINTMENT_STATUS[row["status"]]
    participation = "declined" if status == "cancelled" else "accepted"
    result: dict[str, Any] = {
        "status": status,
        "start": row["start_time"],
        "end": row["end_time"],
        "appointmentType": r4_text(row["type"]),
        "participant": [
            {"actor": ref("Patient", row["patient_id"]), "status": participation},
            {"actor": ref("Practitioner", row["staff_id"]), "status": participation},
        ],
    }
    if row["notes"]:
        result["comment"] = row["notes"]
    return result


def encounter_resource(row: Any, _session: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "finished",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
        },
        "subject": ref("Patient", row["patient_id"]),
        "participant": [{"individual": ref("Practitioner", row["staff_id"])}],
        "period": {"start": row["visit_date"]},
        "diagnosis": [{"condition": ref("Condition", row["record_id"])}],
    }
    if row["chief_complaint"]:
        result["reasonCode"] = [r4_text(row["chief_complaint"])]
    return result


def condition_resource(row: Any, _session: Any) -> dict[str, Any]:
    return {
        "subject": ref("Patient", row["patient_id"]),
        "encounter": ref("Encounter", row["record_id"]),
        "recordedDate": row["visit_date"],
        "code": {
            "coding": [
                {
                    "system": ICD10_SYSTEM,
                    "code": row["icd10_code"],
                    "display": row["description"],
                }
            ],
            "text": row["diagnosis"] or row["description"],
        },
    }


def medication_resource(row: Any, _session: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "unknown",
        "intent": "order",
        "medicationCodeableConcept": r4_text(row["medication"]),
        "subject": ref("Patient", row["patient_id"]),
        "encounter": ref("Encounter", row["record_id"]),
    }
    dosage = ", ".join(
        row[key]
        for key in ("dose", "frequency", "duration", "instructions")
        if row[key]
    )
    if dosage:
        result["dosageInstruction"] = [r4_text(dosage)]
    return result


def care_plan_resource(row: Any, _session: Any) -> dict[str, Any]:
    period: dict[str, Any] = {"start": row["start_date"]}
    if row["end_date"]:
        period["end"] = row["end_date"]
    result: dict[str, Any] = {
        "status": "revoked" if row["status"] == "stopped" else row["status"],
        "intent": "plan",
        "subject": ref("Patient", row["patient_id"]),
        "title": row["title"],
        "period": period,
        "author": ref("Practitioner", row["staff_id"]),
    }
    if row["goal"]:
        result["description"] = row["goal"]
    return result


def procedure_resource(row: Any, _session: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "completed",
        "code": r4_text("Rehabilitation session"),
        "subject": ref("Patient", row["patient_id"]),
        "performedDateTime": row["session_date"],
        "basedOn": [ref("CarePlan", row["plan_id"])],
    }
    notes = [r4_text(row[key]) for key in ("exercises", "notes") if row[key]]
    if notes:
        result["note"] = notes
    return result


def observation_resource(row: Any, _session: Any) -> dict[str, Any]:
    metric = row["metric"]
    quantity: dict[str, Any] = {"value": row["measurement"], "unit": "score"}
    if metric == "rom":
        quantity.update(unit="degrees", system="http://unitsofmeasure.org", code="deg")
    return {
        "status": "final",
        "code": r4_text(REHAB_METRICS[metric]),
        "subject": ref("Patient", row["patient_id"]),
        "effectiveDateTime": row["session_date"],
        "partOf": [ref("Procedure", row["session_id"])],
        "valueQuantity": quantity,
    }


def imaging_resource(row: Any, _session: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "identifier": [
            {"system": "urn:dicom:uid", "value": f"urn:oid:{row['study_uid']}"}
        ],
        "status": "available",
        "subject": ref("Patient", row["patient_id"]),
    }
    if row["record_id"] is not None:
        result["encounter"] = ref("Encounter", row["record_id"])
    if row["study_date"]:
        result["started"] = row["study_date"]
    if row["modality"]:
        result["modality"] = [
            {
                "system": "http://dicom.nema.org/resources/ontology/DCM",
                "code": row["modality"],
            }
        ]
    if row["body_part"]:
        result["description"] = row["body_part"]
    return result


def diagnostic_report_resource(row: Any, _session: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": REPORT_STATUS[row["review_status"]],
        "code": r4_text("Orthopedic scan analysis"),
        "subject": ref("Patient", row["patient_id"]),
        "imagingStudy": [ref("ImagingStudy", row["scan_id"])],
    }
    if row["record_id"] is not None:
        result["encounter"] = ref("Encounter", row["record_id"])
    if row["study_date"]:
        result["effectiveDateTime"] = row["study_date"]
    if row["reviewed_by"] is not None:
        result["resultsInterpreter"] = [ref("Practitioner", row["reviewed_by"])]
    if row["report_text"] or row["finding"]:
        result["conclusion"] = row["report_text"] or row["finding"]
    return result


def money(value: Any) -> dict[str, Any]:
    return {"value": value, "currency": "EGP"}


def invoice_resource(row: Any, session: Any) -> dict[str, Any]:
    items = session.execute(
        select(InvoiceItem.__table__, Service.name.label("service_name"))
        .select_from(InvoiceItem)
        .join(Service, InvoiceItem.service_id == Service.service_id)
        .where(InvoiceItem.invoice_id == row["invoice_id"])
        .order_by(InvoiceItem.item_id)
    ).mappings()
    subject = ref("Patient", row["patient_id"])
    status = {
        "unpaid": "issued",
        "partial": "issued",
        "paid": "balanced",
        "cancelled": "cancelled",
    }[row["status"]]
    result: dict[str, Any] = {
        "status": status,
        "subject": subject,
        "date": row["issue_date"],
        "totalNet": money(row["total_amount"]),
        "totalGross": money(row["total_amount"]),
    }
    lines = []
    charges = []
    for number, item in enumerate(items, 1):
        charge_id = f"charge-{item['item_id']}"
        charges.append(
            {
                "resourceType": "ChargeItem",
                "id": charge_id,
                "status": "billed",
                "code": r4_text(item["service_name"]),
                "subject": subject,
                "quantity": {"value": item["quantity"]},
            }
        )
        lines.append(
            {
                "sequence": number,
                "chargeItemReference": {"reference": f"#{charge_id}"},
                "priceComponent": [
                    {
                        "type": "base",
                        "amount": money(item["quantity"] * item["unit_price"]),
                    }
                ],
            }
        )
    if lines:
        result.update(contained=charges, lineItem=lines)
    return result


def payment_resource(row: Any, _session: Any) -> dict[str, Any]:
    amount = money(row["amount"])
    payment_date = row["paid_at"].date()
    return {
        "status": "active",
        "created": row["paid_at"],
        "paymentDate": payment_date,
        "amount": amount,
        "request": ref("Invoice", row["invoice_id"]),
        "paymentStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/paymentstatus",
                    "code": "paid",
                }
            ]
        },
        "payment": {"reference": "#reconciliation"},
        "recipient": {"reference": "#recipient"},
        "contained": [
            {
                "resourceType": "Organization",
                "id": "recipient",
                "name": "Orthopedic and Rehabilitation Clinic",
            },
            {
                "resourceType": "PaymentReconciliation",
                "id": "reconciliation",
                "status": "active",
                "created": row["paid_at"],
                "paymentDate": payment_date,
                "paymentAmount": amount,
            },
        ],
    }


@dataclass(frozen=True)
class Mapping:
    query: Any
    identity: Any
    owner: Any
    to_resource: Any
    patient_filter: str | None = "patient"
    clinical: bool = True


clinical_sessions = RehabSession.__table__.join(
    TreatmentPlan.__table__, RehabSession.plan_id == TreatmentPlan.plan_id
)
observations = union_all(
    *[
        select(
            (cast(RehabSession.session_id, String) + "-" + metric).label(
                "observation_id"
            ),
            RehabSession.session_id,
            RehabSession.session_date,
            TreatmentPlan.patient_id,
            literal(metric).label("metric"),
            field.label("measurement"),
        )
        .select_from(clinical_sessions)
        .where(field.is_not(None))
        for metric, field in (
            ("pain", RehabSession.pain_score),
            ("rom", RehabSession.range_of_motion),
        )
    ]
).subquery()

MAPPINGS = {
    "Patient": Mapping(
        select(Patient.__table__),
        Patient.__table__.c.patient_id,
        Patient.__table__.c.patient_id,
        patient_resource,
        None,
        False,
    ),
    "Practitioner": Mapping(
        select(Staff.__table__),
        Staff.__table__.c.staff_id,
        None,
        practitioner_resource,
        None,
        False,
    ),
    "Appointment": Mapping(
        select(Appointment.__table__),
        Appointment.__table__.c.appointment_id,
        Appointment.__table__.c.patient_id,
        appointment_resource,
        "patient",
        False,
    ),
    "Encounter": Mapping(
        select(MedicalRecord.__table__),
        MedicalRecord.__table__.c.record_id,
        MedicalRecord.__table__.c.patient_id,
        encounter_resource,
    ),
    "Condition": Mapping(
        select(MedicalRecord.__table__, Icd10Code.description).select_from(
            MedicalRecord.__table__.join(
                Icd10Code.__table__, MedicalRecord.icd10_code == Icd10Code.code
            )
        ),
        MedicalRecord.__table__.c.record_id,
        MedicalRecord.__table__.c.patient_id,
        condition_resource,
    ),
    "MedicationRequest": Mapping(
        select(Prescription.__table__, MedicalRecord.patient_id).select_from(
            Prescription.__table__.join(
                MedicalRecord.__table__,
                Prescription.record_id == MedicalRecord.record_id,
            )
        ),
        Prescription.__table__.c.prescription_id,
        MedicalRecord.__table__.c.patient_id,
        medication_resource,
    ),
    "CarePlan": Mapping(
        select(TreatmentPlan.__table__),
        TreatmentPlan.__table__.c.plan_id,
        TreatmentPlan.__table__.c.patient_id,
        care_plan_resource,
    ),
    "Procedure": Mapping(
        select(RehabSession.__table__, TreatmentPlan.patient_id).select_from(
            clinical_sessions
        ),
        RehabSession.__table__.c.session_id,
        TreatmentPlan.__table__.c.patient_id,
        procedure_resource,
    ),
    "Observation": Mapping(
        select(observations),
        observations.c.observation_id,
        observations.c.patient_id,
        observation_resource,
    ),
    "ImagingStudy": Mapping(
        select(Scan.__table__),
        Scan.__table__.c.scan_id,
        Scan.__table__.c.patient_id,
        imaging_resource,
    ),
    "DiagnosticReport": Mapping(
        select(
            CdssResult.__table__,
            Scan.patient_id,
            Scan.record_id,
            Scan.study_date,
        ).select_from(
            CdssResult.__table__.join(
                Scan.__table__, CdssResult.scan_id == Scan.scan_id
            )
        ),
        CdssResult.__table__.c.result_id,
        Scan.__table__.c.patient_id,
        diagnostic_report_resource,
    ),
    "Invoice": Mapping(
        select(Invoice.__table__),
        Invoice.__table__.c.invoice_id,
        Invoice.__table__.c.patient_id,
        invoice_resource,
        "subject",
        False,
    ),
    "PaymentNotice": Mapping(
        select(Payment.__table__, Invoice.patient_id)
        .select_from(
            Payment.__table__.join(
                Invoice.__table__, Payment.invoice_id == Invoice.invoice_id
            )
        )
        .where(Payment.status == PaymentStatus.success),
        Payment.__table__.c.payment_id,
        Invoice.__table__.c.patient_id,
        payment_resource,
        None,
        False,
    ),
}
