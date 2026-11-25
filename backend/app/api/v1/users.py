"""F03 admin user-management endpoints."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import outerjoin

from app.api.v1.responses import list_response
from app.api.v1.serializers import serialize_user
from app.auth import current_actor, load_actor, require_admin, write_audit
from app.errors import ApiError, FieldError
from app.extensions import bcrypt, db
from app.models import Patient, Staff, StaffType, User, UserRole
from app.schemas import (
    ValidationError,
    as_bool,
    as_choice,
    as_email,
    as_int,
    as_password,
    as_phone,
    as_query_bool,
    as_text,
    like_pattern,
    require_object,
)

users_bp = Blueprint("users", __name__, url_prefix="/users")
users_bp.before_request(load_actor)

MANAGEABLE_ROLES = (UserRole.admin.value, UserRole.staff.value)


def _staff_fields(payload: dict[str, Any], *, required: bool) -> dict[str, Any]:
    """Validate fields used to create or update a staff profile."""
    full_name = as_text(
        payload.get("full_name"), "full_name", max_length=150, required=required
    )
    staff_type_value = as_choice(
        payload.get("staff_type"), "staff_type", StaffType, required=required
    )
    specialty = as_text(
        payload.get("specialty"), "specialty", max_length=100, required=False
    )
    license_no = as_text(
        payload.get("license_no"), "license_no", max_length=50, required=False
    )
    phone = as_phone(payload.get("phone"), required=False)
    return {
        "full_name": full_name,
        "staff_type": staff_type_value,
        "specialty": specialty,
        "license_no": license_no,
        "phone": phone,
    }


def _apply_staff_fields(staff: Staff, values: dict[str, Any]) -> None:
    """Apply validated optional staff fields to an existing profile."""
    if values["full_name"] is not None:
        staff.full_name = values["full_name"]
    if values["staff_type"] is not None:
        staff.staff_type = StaffType(values["staff_type"])
    if values["specialty"] is not None:
        staff.specialty = values["specialty"]
    if values["license_no"] is not None:
        staff.license_no = values["license_no"]
    if values["phone"] is not None:
        staff.phone = values["phone"]


@users_bp.get("")
@require_admin
def list_users() -> Response:
    """List accounts with pagination and optional role/status/search filters."""
    page = as_int(request.args.get("page"), "page", required=False) or 1
    page_size = (
        as_int(
            request.args.get("page_size"),
            "page_size",
            maximum=100,
            required=False,
        )
        or 25
    )
    role_value = as_choice(request.args.get("role"), "role", UserRole, required=False)
    is_active = as_query_bool(
        request.args.get("is_active"), "is_active", required=False
    )
    search_term = request.args.get("q") or request.args.get("search")
    search = as_text(search_term, "search", max_length=150, required=False)

    filters: list[Any] = []
    if role_value is not None:
        filters.append(User.role == UserRole(role_value))
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    if search is not None:
        pattern = like_pattern(search)
        filters.append(
            or_(
                User.email.ilike(pattern, escape="\\"),
                Patient.full_name.ilike(pattern, escape="\\"),
                Staff.full_name.ilike(pattern, escape="\\"),
            )
        )

    joins = outerjoin(
        outerjoin(User, Patient, Patient.user_id == User.user_id),
        Staff,
        Staff.user_id == User.user_id,
    )
    count_statement = (
        select(func.count(User.user_id)).select_from(joins).where(*filters)
    )
    total = db.session.scalar(count_statement) or 0

    statement = (
        select(User)
        .select_from(joins)
        .where(*filters)
        .order_by(User.user_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [serialize_user(user) for user in db.session.scalars(statement).all()]
    return list_response(items, total=total, page=page, page_size=page_size)


@users_bp.post("")
@require_admin
def create_user() -> tuple[Response, int]:
    """Create an admin account or a staff account with its linked profile."""
    payload = require_object(request.get_json(silent=True))
    email = as_email(payload.get("email"))
    password = as_password(payload.get("password"))
    role_value = as_choice(payload.get("role"), "role", MANAGEABLE_ROLES)
    if role_value is None:
        raise ValidationError(
            [FieldError("role", "This field is required.", "required")]
        )
    role = UserRole(role_value)

    staff_values = (
        _staff_fields(payload, required=True)
        if role is UserRole.staff
        else {"full_name": None, "staff_type": None}
    )
    if role is UserRole.staff and (
        staff_values["full_name"] is None or staff_values["staff_type"] is None
    ):
        raise ValidationError(
            [
                FieldError(
                    "staff_type",
                    "A staff type and full name are required for staff accounts.",
                    "required",
                )
            ]
        )

    if db.session.scalar(select(User.user_id).where(User.email == email)) is not None:
        raise ApiError(
            409, "email_exists", "An account with this email already exists."
        )

    user = User(
        email=email,
        password_hash=bcrypt.generate(password),
        role=role,
        is_active=True,
    )
    db.session.add(user)
    db.session.flush()

    if role is UserRole.staff:
        db.session.add(
            Staff(
                user_id=user.user_id,
                full_name=staff_values["full_name"],
                staff_type=StaffType(staff_values["staff_type"]),
                specialty=staff_values["specialty"],
                license_no=staff_values["license_no"],
                phone=staff_values["phone"],
            )
        )

    write_audit("user_created", f"user:{user.user_id}")
    response = jsonify(serialize_user(user))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            409, "email_exists", "An account with this email already exists."
        ) from exc
    return response, 201


@users_bp.patch("/<int:user_id>")
@require_admin
def update_user(user_id: int) -> Response:
    """Change an account's role and activation state, or its staff profile."""
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError(404, "not_found", "The requested user was not found.")

    payload = require_object(request.get_json(silent=True))
    if not payload:
        raise ValidationError(
            [FieldError("body", "At least one field is required.", "required")]
        )

    role_value = as_choice(
        payload.get("role"), "role", MANAGEABLE_ROLES, required=False
    )
    is_active = as_bool(payload.get("is_active"), "is_active", required=False)
    wants_staff_update = any(
        field in payload
        for field in ("full_name", "staff_type", "specialty", "license_no", "phone")
    )
    staff_values = _staff_fields(payload, required=False) if wants_staff_update else {}
    staff = user.staff_profile
    next_role = UserRole(role_value) if role_value is not None else user.role

    if user.user_id == current_actor().user_id:
        if is_active is False:
            raise ApiError(
                400, "bad_request", "You cannot deactivate your own account."
            )
        if role_value is not None and next_role is not UserRole.admin:
            raise ApiError(400, "bad_request", "You cannot change your own admin role.")

    if staff is None and wants_staff_update and next_role is not UserRole.staff:
        raise ValidationError(
            [
                FieldError(
                    "role",
                    "A staff profile requires the staff role.",
                    "invalid",
                )
            ]
        )
    if (
        next_role is UserRole.staff
        and staff is None
        and (
            not wants_staff_update
            or staff_values.get("full_name") is None
            or staff_values.get("staff_type") is None
        )
    ):
        raise ValidationError(
            [
                FieldError(
                    "staff_type",
                    "A staff type and full name are required for staff accounts.",
                    "required",
                )
            ]
        )

    if role_value is not None:
        user.role = next_role
    if is_active is not None:
        user.is_active = is_active

    if staff is not None:
        if wants_staff_update:
            _apply_staff_fields(staff, staff_values)
    elif wants_staff_update:
        user.staff_profile = Staff(
            user_id=user.user_id,
            full_name=staff_values["full_name"],
            staff_type=StaffType(staff_values["staff_type"]),
            specialty=staff_values.get("specialty"),
            license_no=staff_values.get("license_no"),
            phone=staff_values.get("phone"),
        )

    write_audit("user_updated", f"user:{user.user_id}")
    response = jsonify(serialize_user(user))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            409, "conflict", "The update conflicts with existing data."
        ) from exc
    return response
