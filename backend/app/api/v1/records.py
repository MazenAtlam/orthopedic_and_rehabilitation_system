"""F06 musculoskeletal EMR and F07 prescription endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.v1.responses import list_response
from app.auth import (
    can_read_record,
    current_actor,
    load_actor,
    require_clinical_staff,
    require_patient_access,
    require_patient_or_staff,
    write_audit,
)
from app.errors import ApiError, FieldError
from app.extensions import db
from app.models import (
    Icd10Code,
    MedicalRecord,
    Patient,
    Prescription,
)
from app.schemas import (
    ValidationError,
    as_date,
    as_int,
    as_text,
    collect,
    pagination,
    require_object,
)

# Routes carry their full paths: clinical records and patient-owned listings
# share this blueprint so F06 and F07 stay in one module.
records_bp = Blueprint("records", __name__)
records_bp.before_request(load_actor)

RECORD_EDITABLE_FIELDS = frozenset(
    {
        "visit_date",
        "chief_complaint",
        "affected_area",
        "diagnosis",
        "icd10_code",
        "notes",
    }
)


def _serialize(record: MedicalRecord) -> dict[str, Any]:
    """Return the clinical and reference fields of a visit record."""
    return {
        "record_id": record.record_id,
        "patient_id": record.patient_id,
        "staff_id": record.staff_id,
        "visit_date": record.visit_date.isoformat(),
        "chief_complaint": record.chief_complaint,
        "affected_area": record.affected_area,
        "diagnosis": record.diagnosis,
        "icd10_code": record.icd10_code,
        "icd10_description": record.icd10.description,
        "staff_name": record.staff.full_name,
        "notes": record.notes,
    }


def _serialize_prescription(prescription: Prescription) -> dict[str, Any]:
    """Return a prescription with its owning patient and visit identifiers."""
    return {
        "prescription_id": prescription.prescription_id,
        "record_id": prescription.record_id,
        "patient_id": prescription.record.patient_id,
        "visit_date": prescription.record.visit_date.isoformat(),
        "medication": prescription.medication,
        "dose": prescription.dose,
        "frequency": prescription.frequency,
        "duration": prescription.duration,
        "instructions": prescription.instructions,
    }


def _staff_actor_id() -> int:
    """Return the authenticated clinician's staff id."""
    actor = current_actor()
    if not actor.is_staff or actor.staff_id is None:
        raise ApiError(403, "forbidden", "Clinical staff access is required.")
    return actor.staff_id


def _get_patient(patient_id: int) -> Patient:
    """Return a patient or raise a 404 error."""
    patient = db.session.get(Patient, patient_id)
    if patient is None:
        raise ApiError(404, "not_found", "The requested patient was not found.")
    return patient


def _get_record(record_id: int) -> MedicalRecord:
    """Return a medical record or raise a 404 error."""
    record = db.session.get(MedicalRecord, record_id)
    if record is None:
        raise ApiError(404, "not_found", "The requested medical record was not found.")
    return record


def _require_record_access(record: MedicalRecord) -> None:
    """Allow clinical staff or the owning patient to read a record."""
    if not can_read_record(record.patient_id):
        raise ApiError(
            403, "forbidden", "You can only access your own medical records."
        )


def _assert_known_icd10(code: str) -> None:
    """Reject a diagnosis code that is absent from the ICD-10 reference table."""
    if db.session.get(Icd10Code, code) is None:
        raise ValidationError(
            [FieldError("icd10_code", "Unknown ICD-10 code.", "not_found")]
        )


def _collect_optional_text(
    payload: dict[str, Any],
    field: str,
    limit: int,
    errors: list[FieldError],
) -> str | None:
    """Collect one optional text field without leaking its lambda scope."""
    return collect(
        errors,
        lambda: as_text(payload[field], field, max_length=limit, required=False),
    )


@records_bp.get("/patients/<int:patient_id>/records")
@require_patient_or_staff()
def list_patient_records(patient_id: int) -> Response:
    """List one patient's medical history for staff or the owning patient."""
    require_patient_access(patient_id, allow_staff=True, allow_admin=False)
    _get_patient(patient_id)
    page, page_size = pagination(request.args)

    total = (
        db.session.scalar(
            select(func.count())
            .select_from(MedicalRecord)
            .where(MedicalRecord.patient_id == patient_id)
        )
        or 0
    )
    records = db.session.scalars(
        select(MedicalRecord)
        .where(MedicalRecord.patient_id == patient_id)
        .order_by(MedicalRecord.visit_date.desc(), MedicalRecord.record_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    write_audit("medical_history_viewed", f"patient:{patient_id}")
    response = list_response(
        [_serialize(record) for record in records],
        total=total,
        page=page,
        page_size=page_size,
    )
    db.session.commit()
    return response


@records_bp.post("/records")
@require_clinical_staff()
def create_record() -> tuple[Response, int]:
    """Create an ICD-10-coded visit record for a patient."""
    payload = require_object(request.get_json(silent=True))
    errors: list[FieldError] = []

    patient_id = collect(
        errors, lambda: as_int(payload.get("patient_id"), "patient_id")
    )
    visit_date = collect(
        errors,
        lambda: as_date(payload.get("visit_date"), "visit_date", required=False),
    )
    chief_complaint = collect(
        errors,
        lambda: as_text(
            payload.get("chief_complaint"),
            "chief_complaint",
            max_length=2000,
            required=False,
        ),
    )
    affected_area = collect(
        errors,
        lambda: as_text(
            payload.get("affected_area"),
            "affected_area",
            max_length=100,
            required=False,
        ),
    )
    diagnosis = collect(
        errors,
        lambda: as_text(
            payload.get("diagnosis"), "diagnosis", max_length=2000, required=False
        ),
    )
    icd10_code = collect(
        errors, lambda: as_text(payload.get("icd10_code"), "icd10_code", max_length=10)
    )
    notes = collect(
        errors,
        lambda: as_text(payload.get("notes"), "notes", max_length=5000, required=False),
    )

    if errors:
        raise ValidationError(errors)
    if patient_id is None or icd10_code is None:
        raise ValidationError(
            [FieldError("body", "Required record fields are missing.", "required")]
        )

    code = icd10_code.upper()
    _get_patient(patient_id)
    _assert_known_icd10(code)

    record = MedicalRecord(
        patient_id=patient_id,
        staff_id=_staff_actor_id(),
        visit_date=visit_date or date.today(),
        chief_complaint=chief_complaint,
        affected_area=affected_area,
        diagnosis=diagnosis,
        icd10_code=code,
        notes=notes,
    )
    db.session.add(record)
    db.session.flush()
    write_audit("medical_record_created", f"record:{record.record_id}")
    response = jsonify(_serialize(record))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            409, "conflict", "The record conflicts with existing data."
        ) from exc
    return response, 201


@records_bp.get("/records/<int:record_id>")
@require_patient_or_staff()
def get_record(record_id: int) -> Response:
    """Return one medical record to a clinician or its owning patient."""
    record = _get_record(record_id)
    _require_record_access(record)
    write_audit("medical_record_viewed", f"record:{record_id}")
    response = jsonify(_serialize(record))
    db.session.commit()
    return response


@records_bp.put("/records/<int:record_id>")
@require_clinical_staff()
def update_record(record_id: int) -> Response:
    """Update clinical visit fields without changing patient or clinician."""
    record = _get_record(record_id)
    payload = require_object(request.get_json(silent=True))
    errors: list[FieldError] = []
    values: dict[str, Any] = {}

    if not any(field in payload for field in RECORD_EDITABLE_FIELDS):
        errors.append(
            FieldError("body", "At least one editable field is required.", "required")
        )

    if "visit_date" in payload:
        visit_value = collect(
            errors, lambda: as_date(payload["visit_date"], "visit_date")
        )
        if visit_value is not None:
            values["visit_date"] = visit_value
    for field, limit in (
        ("chief_complaint", 2000),
        ("affected_area", 100),
        ("diagnosis", 2000),
        ("notes", 5000),
    ):
        if field in payload:
            values[field] = _collect_optional_text(payload, field, limit, errors)
    if "icd10_code" in payload:
        code_value = collect(
            errors, lambda: as_text(payload["icd10_code"], "icd10_code", max_length=10)
        )
        if code_value is not None:
            values["icd10_code"] = code_value.upper()

    if errors:
        raise ValidationError(errors)
    if "icd10_code" in values:
        _assert_known_icd10(str(values["icd10_code"]))

    for field, value in values.items():
        setattr(record, field, value)
    write_audit("medical_record_updated", f"record:{record_id}")
    response = jsonify(_serialize(record))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            409, "conflict", "The update conflicts with existing data."
        ) from exc
    return response


@records_bp.post("/records/<int:record_id>/prescriptions")
@require_clinical_staff()
def create_prescription(record_id: int) -> tuple[Response, int]:
    """Add a prescription to an existing visit record."""
    _get_record(record_id)
    payload = require_object(request.get_json(silent=True))
    errors: list[FieldError] = []

    medication = collect(
        errors, lambda: as_text(payload.get("medication"), "medication", max_length=150)
    )
    dose = collect(
        errors,
        lambda: as_text(payload.get("dose"), "dose", max_length=50, required=False),
    )
    frequency = collect(
        errors,
        lambda: as_text(
            payload.get("frequency"), "frequency", max_length=50, required=False
        ),
    )
    duration = collect(
        errors,
        lambda: as_text(
            payload.get("duration"), "duration", max_length=50, required=False
        ),
    )
    instructions = collect(
        errors,
        lambda: as_text(
            payload.get("instructions"), "instructions", max_length=5000, required=False
        ),
    )

    if errors:
        raise ValidationError(errors)
    if medication is None:
        raise ValidationError(
            [FieldError("medication", "This field is required.", "required")]
        )

    prescription = Prescription(
        record_id=record_id,
        medication=medication,
        dose=dose,
        frequency=frequency,
        duration=duration,
        instructions=instructions,
    )
    db.session.add(prescription)
    db.session.flush()
    write_audit("prescription_created", f"prescription:{prescription.prescription_id}")
    response = jsonify(_serialize_prescription(prescription))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            409, "conflict", "The prescription conflicts with existing data."
        ) from exc
    return response, 201


@records_bp.get("/patients/<int:patient_id>/prescriptions")
@require_patient_or_staff()
def list_patient_prescriptions(patient_id: int) -> Response:
    """List a patient's prescriptions for staff or the owning patient."""
    require_patient_access(patient_id, allow_staff=True, allow_admin=False)
    _get_patient(patient_id)
    page, page_size = pagination(request.args)
    join = MedicalRecord.record_id == Prescription.record_id

    total = (
        db.session.scalar(
            select(func.count())
            .select_from(Prescription)
            .join(MedicalRecord, join)
            .where(MedicalRecord.patient_id == patient_id)
        )
        or 0
    )
    prescriptions = db.session.scalars(
        select(Prescription)
        .join(MedicalRecord, join)
        .where(MedicalRecord.patient_id == patient_id)
        .order_by(Prescription.prescription_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    write_audit("prescriptions_viewed", f"patient:{patient_id}")
    response = list_response(
        [_serialize_prescription(prescription) for prescription in prescriptions],
        total=total,
        page=page,
        page_size=page_size,
    )
    db.session.commit()
    return response
