"""JWT-to-database identity adapter used by protected blueprints."""

from __future__ import annotations

from flask import g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy import select
from sqlalchemy.orm import outerjoin

from app.auth.permissions import Actor
from app.errors import ApiError
from app.extensions import db
from app.models import Patient, Staff, StaffType, User, UserRole

MAX_ID = 2_147_483_647


def _valid_identity(identity: object) -> int | None:
    """Return a numeric user id from a JWT subject, or ``None`` when invalid."""
    subject = identity if isinstance(identity, (str, int)) else ""
    if isinstance(subject, bool):
        return None
    text = str(subject)
    if not text.isascii() or not text.isdecimal() or len(text) > 10:
        return None
    user_id = int(text)
    return user_id if 0 < user_id <= MAX_ID else None


def load_actor() -> None:
    """Verify the bearer token and load the active account into ``flask.g``."""
    verify_jwt_in_request(optional=True)
    user_id = _valid_identity(get_jwt_identity())
    if user_id is None:
        raise ApiError(401, "login", "Invalid account.")

    statement = (
        select(
            User.user_id,
            User.role,
            Patient.patient_id,
            Staff.staff_id,
            Staff.staff_type,
        )
        .select_from(
            outerjoin(
                outerjoin(User, Patient, Patient.user_id == User.user_id),
                Staff,
                Staff.user_id == User.user_id,
            )
        )
        .where(User.user_id == user_id, User.is_active.is_(True))
    )
    row = db.session.execute(statement).one_or_none()
    if row is None:
        raise ApiError(401, "login", "Account is unavailable.")

    role = row.role
    role_value = role.value if isinstance(role, UserRole) else str(role)
    try:
        actor_role = UserRole(role_value)
    except ValueError as exc:
        raise ApiError(401, "login", "Account has an invalid role.") from exc

    staff_type_value = row.staff_type
    staff_type: StaffType | None = None
    if staff_type_value is not None:
        value = (
            staff_type_value.value
            if isinstance(staff_type_value, StaffType)
            else str(staff_type_value)
        )
        try:
            staff_type = StaffType(value)
        except ValueError as exc:
            raise ApiError(401, "login", "Account has an invalid staff type.") from exc

    if actor_role is UserRole.patient and row.patient_id is None:
        raise ApiError(401, "login", "Patient profile is unavailable.")
    if actor_role is UserRole.staff and row.staff_id is None:
        raise ApiError(401, "login", "Staff profile is unavailable.")

    g.actor = Actor(
        user_id=int(row.user_id),
        role=actor_role,
        patient_id=row.patient_id,
        staff_id=row.staff_id,
        staff_type=staff_type,
    )
