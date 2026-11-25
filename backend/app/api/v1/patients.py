"""F04 patient profile endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.v1.responses import list_response
from app.auth import (
    load_actor,
    require_admin_or_staff,
    require_patient_access,
    write_audit,
)
from app.errors import ApiError, FieldError
from app.extensions import db
from app.models import Gender, Patient
from app.schemas import (
    ValidationError,
    as_choice,
    as_date,
    as_phone,
    as_text,
    like_pattern,
    pagination,
    require_object,
)

patients_bp = Blueprint("patients", __name__, url_prefix="/patients")
patients_bp.before_request(load_actor)

EDITABLE_FIELDS = frozenset(
    {
        "full_name",
        "birth_date",
        "gender",
        "phone",
        "address",
        "national_id",
        "emergency_contact",
    }
)


def _serialize(patient: Patient) -> dict[str, Any]:
    """Return the patient profile fields used by every F04 response."""
    return {
        "patient_id": patient.patient_id,
        "user_id": patient.user_id,
        "full_name": patient.full_name,
        "birth_date": patient.birth_date.isoformat(),
        "gender": patient.gender.value,
        "phone": patient.phone,
        "address": patient.address,
        "national_id": patient.national_id,
        "emergency_contact": patient.emergency_contact,
    }


def _validate_updates(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate all submitted profile fields and collect every field error."""
    errors: list[FieldError] = []
    values: dict[str, Any] = {}

    if not any(field in payload for field in EDITABLE_FIELDS):
        errors.append(
            FieldError("body", "At least one editable field is required.", "required")
        )

    if "full_name" in payload:
        try:
            name_value = as_text(payload["full_name"], "full_name", max_length=150)
            if name_value is None:
                raise ValidationError(
                    [FieldError("full_name", "This field is required.", "required")]
                )
            values["full_name"] = name_value
        except ValidationError as exc:
            errors.extend(exc.errors)

    if "birth_date" in payload:
        try:
            birth_value = as_date(payload["birth_date"], "birth_date")
            if birth_value is None:
                raise ValidationError(
                    [FieldError("birth_date", "This field is required.", "required")]
                )
            if birth_value > date.today():
                raise ValidationError(
                    [
                        FieldError(
                            "birth_date",
                            "Must be today or earlier.",
                            "out_of_range",
                        )
                    ]
                )
            values["birth_date"] = birth_value
        except ValidationError as exc:
            errors.extend(exc.errors)

    if "gender" in payload:
        try:
            gender_value = as_choice(payload["gender"], "gender", Gender)
            if gender_value is None:
                raise ValidationError(
                    [FieldError("gender", "This field is required.", "required")]
                )
            values["gender"] = Gender(gender_value)
        except ValidationError as exc:
            errors.extend(exc.errors)

    if "phone" in payload:
        try:
            values["phone"] = as_phone(payload["phone"], "phone", required=False)
        except ValidationError as exc:
            errors.extend(exc.errors)

    for field, max_length in (
        ("address", 500),
        ("national_id", 20),
        ("emergency_contact", 150),
    ):
        if field in payload:
            try:
                values[field] = as_text(
                    payload[field], field, max_length=max_length, required=False
                )
            except ValidationError as exc:
                errors.extend(exc.errors)

    if errors:
        raise ValidationError(errors)
    return values


@patients_bp.get("")
@require_admin_or_staff()
def list_patients() -> Response:
    """Search and list patients with pagination (admin and clinical staff)."""
    page, page_size = pagination(request.args)
    search_term = request.args.get("q") or request.args.get("search")
    search = as_text(search_term, "search", max_length=150, required=False)
    gender = as_choice(request.args.get("gender"), "gender", Gender, required=False)

    filters: list[Any] = []
    if search is not None:
        pattern = like_pattern(search)
        filters.append(
            or_(
                Patient.full_name.ilike(pattern, escape="\\"),
                Patient.national_id.ilike(pattern, escape="\\"),
                Patient.phone.ilike(pattern, escape="\\"),
            )
        )
    if gender is not None:
        filters.append(Patient.gender == Gender(gender))

    statement = select(Patient).where(*filters)
    total = (
        db.session.scalar(select(func.count()).select_from(Patient).where(*filters))
        or 0
    )
    patients = db.session.scalars(
        statement.order_by(Patient.patient_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list_response(
        [_serialize(patient) for patient in patients],
        total=total,
        page=page,
        page_size=page_size,
    )


@patients_bp.get("/<int:patient_id>")
def get_patient(patient_id: int) -> Response:
    """Return one profile to an admin, a staff member or the owning patient."""
    require_patient_access(patient_id, allow_staff=True, allow_admin=True)
    patient = db.session.get(Patient, patient_id)
    if patient is None:
        raise ApiError(404, "not_found", "The requested patient was not found.")
    write_audit("patient_viewed", f"patient:{patient_id}")
    db.session.commit()
    return jsonify(_serialize(patient))


@patients_bp.put("/<int:patient_id>")
def update_patient(patient_id: int) -> Response:
    """Update a profile; patients may only update their own record."""
    require_patient_access(patient_id, allow_staff=True, allow_admin=True)
    patient = db.session.get(Patient, patient_id)
    if patient is None:
        raise ApiError(404, "not_found", "The requested patient was not found.")

    payload = require_object(request.get_json(silent=True))
    values = _validate_updates(payload)
    for field, value in values.items():
        setattr(patient, field, value)

    write_audit("patient_updated", f"patient:{patient_id}")
    response = jsonify(_serialize(patient))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            409, "conflict", "The update conflicts with existing data."
        ) from exc
    return response
