"""Serializable representations shared by API v1 routes."""

from __future__ import annotations

from typing import Any

from app.models import User


def serialize_user(user: User) -> dict[str, Any]:
    """Return the frontend ``User`` shape for an account.

    The React types require ``full_name`` to be a string, so admin accounts
    without a staff or patient profile fall back to their email address.
    """
    staff = user.staff_profile
    patient = user.patient_profile
    full_name = (
        staff.full_name
        if staff is not None
        else (patient.full_name if patient is not None else user.email)
    )
    return {
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "full_name": full_name,
        "staff_type": staff.staff_type.value if staff is not None else None,
        "specialty": staff.specialty if staff is not None else None,
        "patient_id": patient.patient_id if patient is not None else None,
        "staff_id": staff.staff_id if staff is not None else None,
    }
