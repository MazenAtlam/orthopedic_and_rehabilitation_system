"""Bind the authenticated request to the clinical database account."""

from flask import g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy import select

from app.utils.common import ApiError, db
from app.models.schema_v1 import patient, user


def load_actor():
    verify_jwt_in_request()
    identity = get_jwt_identity()
    if not isinstance(identity, str) or len(identity) > 10 or not identity.isascii() or not identity.isdecimal():
        raise ApiError(401, "login", "Invalid account.")
    if not 0 < int(identity) <= 2_147_483_647:
        raise ApiError(401, "login", "Invalid account.")
    statement = select(
        user.c.user_id, user.c.role, patient.c.patient_id
    ).select_from(user.outerjoin(patient)).where(
        user.c.user_id == int(identity), user.c.is_active.is_(True)
    )
    with db().connect() as connection:
        g.actor = connection.execute(statement).mappings().one_or_none()
    if g.actor is None or (g.actor["role"] == "patient" and not g.actor["patient_id"]):
        raise ApiError(401, "login", "Account is unavailable.")
