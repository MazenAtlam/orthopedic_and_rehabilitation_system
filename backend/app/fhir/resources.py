from dataclasses import dataclass
from typing import Any

from sqlalchemy import String, cast, literal, select, union_all

from app.models.schema_v1 import (
    appointment,
    cdss_result,
    icd10_code,
    invoice,
    invoice_item,
    medical_record,
    patient,
    payment,
    prescription,
    rehab_session,
    scan,
    service,
    staff,
    treatment_plan,
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


def patient_resource(row: Any, _connection: Any) -> dict[str, Any]:
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


def practitioner_resource(row: Any, _connection: Any) -> dict[str, Any]:
    return {"name": [r4_text(row["full_name"])]}


def appointment_resource(row: Any, _connection: Any) -> dict[str, Any]:
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


def encounter_resource(row: Any, _connection: Any) -> dict[str, Any]:
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


def condition_resource(row: Any, _connection: Any) -> dict[str, Any]:
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


def medication_resource(row: Any, _connection: Any) -> dict[str, Any]:
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


def care_plan_resource(row: Any, _connection: Any) -> dict[str, Any]:
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


def procedure_resource(row: Any, _connection: Any) -> dict[str, Any]:
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


def observation_resource(row: Any, _connection: Any) -> dict[str, Any]:
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


def imaging_resource(row: Any, _connection: Any) -> dict[str, Any]:
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


def diagnostic_report_resource(row: Any, _connection: Any) -> dict[str, Any]:
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


def invoice_resource(row: Any, connection: Any) -> dict[str, Any]:
    items = connection.execute(
        select(invoice_item, service.c.name.label("service_name"))
        .select_from(invoice_item.join(service))
        .where(invoice_item.c.invoice_id == row["invoice_id"])
        .order_by(invoice_item.c.item_id)
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


def payment_resource(row: Any, _connection: Any) -> dict[str, Any]:
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


clinical_sessions = rehab_session.join(treatment_plan)
observations = union_all(
    *[
        select(
            (cast(rehab_session.c.session_id, String) + "-" + metric).label(
                "observation_id"
            ),
            rehab_session.c.session_id,
            rehab_session.c.session_date,
            treatment_plan.c.patient_id,
            literal(metric).label("metric"),
            field.label("measurement"),
        )
        .select_from(clinical_sessions)
        .where(field.is_not(None))
        for metric, field in (
            ("pain", rehab_session.c.pain_score),
            ("rom", rehab_session.c.range_of_motion),
        )
    ]
).subquery()

MAPPINGS = {
    "Patient": Mapping(
        select(patient),
        patient.c.patient_id,
        patient.c.patient_id,
        patient_resource,
        None,
        False,
    ),
    "Practitioner": Mapping(
        select(staff), staff.c.staff_id, None, practitioner_resource, None, False
    ),
    "Appointment": Mapping(
        select(appointment),
        appointment.c.appointment_id,
        appointment.c.patient_id,
        appointment_resource,
        "patient",
        False,
    ),
    "Encounter": Mapping(
        select(medical_record),
        medical_record.c.record_id,
        medical_record.c.patient_id,
        encounter_resource,
    ),
    "Condition": Mapping(
        select(medical_record, icd10_code.c.description).select_from(
            medical_record.join(icd10_code)
        ),
        medical_record.c.record_id,
        medical_record.c.patient_id,
        condition_resource,
    ),
    "MedicationRequest": Mapping(
        select(prescription, medical_record.c.patient_id).select_from(
            prescription.join(medical_record)
        ),
        prescription.c.prescription_id,
        medical_record.c.patient_id,
        medication_resource,
    ),
    "CarePlan": Mapping(
        select(treatment_plan),
        treatment_plan.c.plan_id,
        treatment_plan.c.patient_id,
        care_plan_resource,
    ),
    "Procedure": Mapping(
        select(rehab_session, treatment_plan.c.patient_id).select_from(
            clinical_sessions
        ),
        rehab_session.c.session_id,
        treatment_plan.c.patient_id,
        procedure_resource,
    ),
    "Observation": Mapping(
        select(observations),
        observations.c.observation_id,
        observations.c.patient_id,
        observation_resource,
    ),
    "ImagingStudy": Mapping(
        select(scan), scan.c.scan_id, scan.c.patient_id, imaging_resource
    ),
    "DiagnosticReport": Mapping(
        select(
            cdss_result, scan.c.patient_id, scan.c.record_id, scan.c.study_date
        ).select_from(cdss_result.join(scan)),
        cdss_result.c.result_id,
        scan.c.patient_id,
        diagnostic_report_resource,
    ),
    "Invoice": Mapping(
        select(invoice),
        invoice.c.invoice_id,
        invoice.c.patient_id,
        invoice_resource,
        "subject",
        False,
    ),
    "PaymentNotice": Mapping(
        select(payment, invoice.c.patient_id)
        .select_from(payment.join(invoice))
        .where(payment.c.status == "success"),
        payment.c.payment_id,
        invoice.c.patient_id,
        payment_resource,
        None,
        False,
    ),
}
