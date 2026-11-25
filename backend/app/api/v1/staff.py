"""F04 staff listing and availability endpoints."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import func, or_, select

from app.api.v1.responses import list_response
from app.auth import load_actor, require_roles
from app.errors import ApiError
from app.extensions import db
from app.models import Appointment, AppointmentStatus, Staff, StaffType, User, UserRole
from app.schemas import as_choice, as_date, as_text, like_pattern, pagination
from app.services import iso_utc, times_overlap

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")
staff_bp.before_request(load_actor)


def _serialize(staff: Staff) -> dict[str, Any]:
    """Return the public booking fields for a staff member."""
    return {
        "staff_id": staff.staff_id,
        "user_id": staff.user_id,
        "full_name": staff.full_name,
        "staff_type": staff.staff_type.value,
        "specialty": staff.specialty,
        "license_no": staff.license_no,
        "phone": staff.phone,
        "is_active": staff.user.is_active,
    }


@staff_bp.get("")
@require_roles(UserRole.admin, UserRole.staff, UserRole.patient)
def list_staff() -> Response:
    """List active staff members available for appointment booking."""
    page, page_size = pagination(request.args)
    staff_type = as_choice(
        request.args.get("staff_type"), "staff_type", StaffType, required=False
    )
    search_term = request.args.get("q") or request.args.get("search")
    search = as_text(search_term, "search", max_length=150, required=False)

    filters: list[Any] = [User.is_active.is_(True)]
    if staff_type is not None:
        filters.append(Staff.staff_type == StaffType(staff_type))
    if search is not None:
        pattern = like_pattern(search)
        filters.append(
            or_(
                Staff.full_name.ilike(pattern, escape="\\"),
                Staff.specialty.ilike(pattern, escape="\\"),
            )
        )

    base = select(Staff).join(User, Staff.user_id == User.user_id)
    total = (
        db.session.scalar(
            select(func.count())
            .select_from(Staff)
            .join(User, Staff.user_id == User.user_id)
            .where(*filters)
        )
        or 0
    )
    members = db.session.scalars(
        base.where(*filters)
        .order_by(Staff.staff_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list_response(
        [_serialize(member) for member in members],
        total=total,
        page=page,
        page_size=page_size,
    )


@staff_bp.get("/<int:staff_id>/availability")
@require_roles(UserRole.admin, UserRole.staff, UserRole.patient)
def staff_availability(staff_id: int) -> Response:
    """Return the free half-hour slots for a staff member on one UTC date."""
    day = as_date(request.args.get("date"), "date", required=False)
    if day is None:
        raise ApiError(400, "bad_request", "A date is required.")

    staff = db.session.get(Staff, staff_id)
    if staff is None or not staff.user.is_active:
        raise ApiError(404, "not_found", "The requested staff member was not found.")

    start_hour = int(current_app.config["SLOT_START_HOUR"])
    end_hour = int(current_app.config["SLOT_END_HOUR"])
    slot_minutes = int(current_app.config["SLOT_MINUTES"])
    midnight = datetime.combine(day, time.min, tzinfo=timezone.utc)
    window_start = midnight + timedelta(hours=start_hour)
    window_end = midnight + timedelta(hours=end_hour)

    booked = db.session.scalars(
        select(Appointment).where(
            Appointment.staff_id == staff_id,
            Appointment.status == AppointmentStatus.booked,
            Appointment.start_time < window_end,
            Appointment.end_time > window_start,
        )
    ).all()

    step = timedelta(minutes=slot_minutes)
    slots: list[dict[str, str]] = []
    cursor = window_start
    while cursor + step <= window_end:
        slot_end = cursor + step
        if not any(
            times_overlap(cursor, slot_end, item.start_time, item.end_time)
            for item in booked
        ):
            slots.append({"start_time": iso_utc(cursor), "end_time": iso_utc(slot_end)})
        cursor = slot_end

    if request.args.get("details", "").lower() in {"1", "true", "yes", "on"}:
        return jsonify(
            {
                "staff_id": staff_id,
                "date": day.isoformat(),
                "slots": slots,
                "available_slots": slots,
            }
        )
    return jsonify([slot["start_time"] for slot in slots])
