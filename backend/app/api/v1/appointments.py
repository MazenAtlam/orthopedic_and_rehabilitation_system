"""F05 appointment endpoints."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.v1.responses import list_response
from app.auth import (
    current_actor,
    load_actor,
    require_roles,
    write_audit,
)
from app.errors import ApiError, FieldError
from app.extensions import db
from app.models import (
    Appointment,
    AppointmentStatus,
    AppointmentType,
    Patient,
    Staff,
    UserRole,
)
from app.schemas import (
    ValidationError,
    as_choice,
    as_date,
    as_datetime,
    as_int,
    as_text,
    pagination,
    require_object,
)
from app.services import appointments_overlap, iso_utc, times_overlap, utc

appointments_bp = Blueprint("appointments", __name__, url_prefix="/appointments")
appointments_bp.before_request(load_actor)

__all__ = ["appointments_bp", "appointments_overlap", "times_overlap"]


def _serialize(appointment: Appointment) -> dict[str, Any]:
    """Return the appointment fields used by every F05 response."""
    return {
        "appointment_id": appointment.appointment_id,
        "patient_id": appointment.patient_id,
        "staff_id": appointment.staff_id,
        "type": appointment.type.value,
        "start_time": iso_utc(appointment.start_time),
        "end_time": iso_utc(appointment.end_time),
        "status": appointment.status.value,
        "notes": appointment.notes,
        "patient_name": appointment.patient.full_name,
        "staff_name": appointment.staff.full_name,
    }


def _parse_window(
    payload: dict[str, Any],
    errors: list[FieldError],
    *,
    require_both: bool,
    current_start: datetime | None = None,
    current_end: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """Parse start/end timestamps and collect window validation errors."""
    start = current_start
    end = current_end

    if require_both or "start_time" in payload:
        try:
            parsed = as_datetime(
                payload.get("start_time"), "start_time", required=require_both
            )
            if parsed is None:
                raise ValidationError(
                    [FieldError("start_time", "This field is required.", "required")]
                )
            start = utc(parsed)
        except ValidationError as exc:
            errors.extend(exc.errors)

    if require_both or "end_time" in payload:
        try:
            parsed = as_datetime(
                payload.get("end_time"), "end_time", required=require_both
            )
            if parsed is None:
                raise ValidationError(
                    [FieldError("end_time", "This field is required.", "required")]
                )
            end = utc(parsed)
        except ValidationError as exc:
            errors.extend(exc.errors)

    if start is not None and end is not None and end <= start:
        errors.append(
            FieldError("end_time", "Must be after start_time.", "out_of_range")
        )
    return start, end


def _assert_no_overlap(
    staff_id: int,
    start: datetime,
    end: datetime,
    *,
    exclude_id: int | None = None,
) -> None:
    """Reject a booked slot that overlaps an existing booked appointment."""
    statement = select(Appointment.appointment_id).where(
        Appointment.staff_id == staff_id,
        Appointment.status == AppointmentStatus.booked,
        Appointment.start_time < end,
        Appointment.end_time > start,
    )
    if exclude_id is not None:
        statement = statement.where(Appointment.appointment_id != exclude_id)
    if db.session.scalar(statement.limit(1)) is not None:
        raise ApiError(
            409,
            "appointment_conflict",
            "The staff member already has a booked appointment at that time.",
        )


def _get_staff(staff_id: int) -> Staff:
    """Return an active staff member or raise a 404 error."""
    staff = db.session.get(Staff, staff_id)
    if staff is None or not staff.user.is_active:
        raise ApiError(404, "not_found", "The requested staff member was not found.")
    return staff


def _get_patient(patient_id: int) -> Patient:
    """Return a patient profile or raise a 404 error."""
    patient = db.session.get(Patient, patient_id)
    if patient is None:
        raise ApiError(404, "not_found", "The requested patient was not found.")
    return patient


@appointments_bp.get("")
def list_appointments() -> Response:
    """List appointments with filters; patients only see their own bookings."""
    actor = current_actor()
    page, page_size = pagination(request.args)
    patient_filter = as_int(
        request.args.get("patient_id") or request.args.get("patient"),
        "patient",
        required=False,
    )
    staff_filter = as_int(
        request.args.get("staff_id") or request.args.get("staff"),
        "staff",
        required=False,
    )
    day = as_date(request.args.get("date"), "date", required=False)
    status = as_choice(
        request.args.get("status"), "status", AppointmentStatus, required=False
    )

    if actor.is_patient:
        if patient_filter is not None and patient_filter != actor.patient_id:
            raise ApiError(
                403, "forbidden", "You can only access your own appointments."
            )
        filters: list[Any] = [Appointment.patient_id == actor.patient_id]
    elif patient_filter is not None:
        filters = [Appointment.patient_id == patient_filter]
    else:
        filters = []

    if staff_filter is not None:
        filters.append(Appointment.staff_id == staff_filter)
    if status is not None:
        filters.append(Appointment.status == AppointmentStatus(status))
    if day is not None:
        lower = datetime.combine(day, time.min, tzinfo=timezone.utc)
        upper = lower + timedelta(days=1)
        filters.append(Appointment.start_time < upper)
        filters.append(Appointment.end_time > lower)

    statement = select(Appointment).where(*filters)
    total = (
        db.session.scalar(select(func.count()).select_from(Appointment).where(*filters))
        or 0
    )
    appointments = db.session.scalars(
        statement.order_by(Appointment.start_time, Appointment.appointment_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list_response(
        [_serialize(item) for item in appointments],
        total=total,
        page=page,
        page_size=page_size,
    )


@appointments_bp.post("")
@require_roles(UserRole.admin, UserRole.staff, UserRole.patient)
def create_appointment() -> tuple[Response, int]:
    """Book a free slot for a patient (own profile only for patients)."""
    payload = require_object(request.get_json(silent=True))
    errors: list[FieldError] = []

    try:
        patient_id = as_int(payload.get("patient_id"), "patient_id")
    except ValidationError as exc:
        errors.extend(exc.errors)
        patient_id = None
    try:
        staff_id = as_int(payload.get("staff_id"), "staff_id")
    except ValidationError as exc:
        errors.extend(exc.errors)
        staff_id = None
    try:
        type_value = as_choice(payload.get("type"), "type", AppointmentType)
    except ValidationError as exc:
        errors.extend(exc.errors)
        type_value = None

    start, end = _parse_window(payload, errors, require_both=True)
    try:
        notes = as_text(payload.get("notes"), "notes", max_length=1000, required=False)
    except ValidationError as exc:
        errors.extend(exc.errors)
        notes = None

    if errors:
        raise ValidationError(errors)
    if start is None or end is None or patient_id is None or staff_id is None:
        raise ValidationError(
            [FieldError("body", "Required appointment fields are missing.", "required")]
        )
    if type_value is None:
        raise ValidationError(
            [FieldError("type", "This field is required.", "required")]
        )

    actor = current_actor()
    if actor.is_patient and actor.patient_id != patient_id:
        raise ApiError(403, "forbidden", "You can only book your own appointments.")

    _get_patient(patient_id)
    _get_staff(staff_id)
    _assert_no_overlap(staff_id, start, end)

    appointment = Appointment(
        patient_id=patient_id,
        staff_id=staff_id,
        type=AppointmentType(type_value),
        start_time=start,
        end_time=end,
        status=AppointmentStatus.booked,
        notes=notes,
    )
    db.session.add(appointment)
    db.session.flush()
    write_audit("appointment_created", f"appointment:{appointment.appointment_id}")
    response = jsonify(_serialize(appointment))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            409,
            "appointment_conflict",
            "The staff member already has a booked appointment at that time.",
        ) from exc
    return response, 201


@appointments_bp.patch("/<int:appointment_id>")
@require_roles(UserRole.admin, UserRole.staff, UserRole.patient)
def update_appointment(appointment_id: int) -> Response:
    """Reschedule an appointment or change its status."""
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None:
        raise ApiError(404, "not_found", "The requested appointment was not found.")

    actor = current_actor()
    if actor.is_patient and actor.patient_id != appointment.patient_id:
        raise ApiError(403, "forbidden", "You can only change your own appointments.")

    payload = require_object(request.get_json(silent=True))
    if not payload:
        raise ValidationError(
            [FieldError("body", "At least one field is required.", "required")]
        )
    errors: list[FieldError] = []
    start, end = _parse_window(
        payload,
        errors,
        require_both=False,
        current_start=appointment.start_time,
        current_end=appointment.end_time,
    )

    previous_status = appointment.status
    status = appointment.status
    if "status" in payload:
        try:
            status_value = as_choice(
                payload["status"], "status", AppointmentStatus, required=False
            )
            if status_value is None:
                raise ValidationError(
                    [FieldError("status", "This field is required.", "required")]
                )
            candidate = AppointmentStatus(status_value)
            if actor.is_patient and candidate is not AppointmentStatus.cancelled:
                raise ApiError(
                    403,
                    "forbidden",
                    "Patients can only cancel an appointment status.",
                )
            status = candidate
        except ValidationError as exc:
            errors.extend(exc.errors)

    notes = appointment.notes
    if "notes" in payload:
        try:
            notes = as_text(payload["notes"], "notes", max_length=1000, required=False)
        except ValidationError as exc:
            errors.extend(exc.errors)

    if errors:
        raise ValidationError(errors)
    if start is None or end is None:
        raise ApiError(500, "internal_error", "The appointment window is invalid.")

    rescheduled = "start_time" in payload or "end_time" in payload
    if status is AppointmentStatus.booked:
        _assert_no_overlap(appointment.staff_id, start, end, exclude_id=appointment_id)

    if rescheduled:
        appointment.start_time = start
        appointment.end_time = end
    appointment.status = status
    appointment.notes = notes

    if rescheduled:
        action = "appointment_rescheduled"
    elif status is not previous_status:
        action = "appointment_status_changed"
    else:
        action = "appointment_updated"
    write_audit(action, f"appointment:{appointment_id}")

    response = jsonify(_serialize(appointment))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            409,
            "appointment_conflict",
            "The staff member already has a booked appointment at that time.",
        ) from exc
    return response


@appointments_bp.delete("/<int:appointment_id>")
@require_roles(UserRole.admin, UserRole.staff, UserRole.patient)
def cancel_appointment(appointment_id: int) -> Response:
    """Cancel an appointment by changing its status, never by deleting it."""
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None:
        raise ApiError(404, "not_found", "The requested appointment was not found.")

    actor = current_actor()
    if actor.is_patient and actor.patient_id != appointment.patient_id:
        raise ApiError(403, "forbidden", "You can only cancel your own appointments.")

    appointment.status = AppointmentStatus.cancelled
    write_audit("appointment_cancelled", f"appointment:{appointment_id}")
    response = jsonify(_serialize(appointment))
    db.session.commit()
    return response
