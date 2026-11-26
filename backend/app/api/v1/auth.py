"""F01 authentication endpoints."""

from __future__ import annotations

from datetime import date
from typing import cast
from urllib.parse import urlsplit

from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import (
    get_jwt_identity,
    set_refresh_cookies,
    unset_refresh_cookies,
    verify_jwt_in_request,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth import (
    claims_for,
    issue_access_token,
    issue_tokens,
    revoke_current_refresh_token,
    write_audit,
)
from app.api.v1.serializers import serialize_user
from app.errors import ApiError, FieldError
from app.extensions import bcrypt, db, login_tracker, revoke_current_token
from app.models import Gender, Patient, User, UserRole
from app.schemas import (
    ValidationError,
    as_choice,
    as_date,
    as_email,
    as_password,
    as_phone,
    as_text,
    collect,
    require_object,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _access_expires_in() -> int:
    """Return the configured access-token lifetime in seconds."""
    expires = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    return int(expires.total_seconds())


def _attempt_key(email: str) -> str:
    """Key login attempts by normalised email and client IP."""
    return login_tracker.key(email, request.remote_addr)


def _lock_error(key: str) -> ApiError:
    """Build a consistent temporary-lock error."""
    remaining = login_tracker.locked_for(key)
    return ApiError(
        429,
        "login_locked",
        "Too many failed attempts. "
        f"Try again in {remaining} second{'s' if remaining != 1 else ''}.",
    )


_DUMMY_PASSWORD_HASH: str | None = None


def _verify_password(password: str, stored_hash: str) -> bool:
    """Run a bcrypt check even for unknown accounts to reduce timing leaks."""
    global _DUMMY_PASSWORD_HASH
    if stored_hash:
        return bcrypt.verify(password, stored_hash)
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = bcrypt.generate("not-a-real-password")
    return bcrypt.verify(password, _DUMMY_PASSWORD_HASH)


def _user_from_identity(identity: object, *, active_only: bool) -> User:
    """Load an account from a JWT subject, optionally requiring it to be active."""
    subject = identity if isinstance(identity, (str, int)) else ""
    if (
        isinstance(subject, bool)
        or not str(subject).isascii()
        or not str(subject).isdecimal()
    ):
        raise ApiError(401, "login", "Invalid token subject.")
    user = db.session.get(User, int(subject))
    if user is None or (active_only and not user.is_active):
        raise ApiError(401, "login", "Account is unavailable.")
    return user


def _active_user_from_identity(identity: object) -> User:
    """Load an active account from a JWT subject."""
    return _user_from_identity(identity, active_only=True)


def _verify_refresh_origin() -> None:
    """Reject cross-site use of the refresh cookie when a browser origin is sent."""
    source = request.headers.get("Origin") or request.headers.get("Referer")
    if not source:
        return
    candidate = urlsplit(source)
    target = urlsplit(request.host_url)
    candidate_host = candidate.hostname
    target_host = target.hostname
    if (
        source.strip().lower() == "null"
        or candidate.scheme.lower() not in {"http", "https"}
        or candidate_host is None
        or target_host is None
        or candidate.scheme.lower() != target.scheme.lower()
        or candidate_host.lower() != target_host.lower()
    ):
        raise ApiError(403, "forbidden", "Cross-site token requests are not allowed.")
    default_port = 443 if target.scheme.lower() == "https" else 80
    try:
        candidate_port = candidate.port or (
            443 if candidate.scheme.lower() == "https" else 80
        )
        target_port = target.port or default_port
    except ValueError as exc:
        raise ApiError(
            403, "forbidden", "Cross-site token requests are not allowed."
        ) from exc
    if candidate_port != target_port:
        raise ApiError(403, "forbidden", "Cross-site token requests are not allowed.")


@auth_bp.post("/register")
def register() -> tuple[Response, int]:
    """Create a patient account and its linked patient profile."""
    payload = require_object(request.get_json(silent=True))
    errors: list[FieldError] = []
    full_name = collect(
        errors,
        lambda: as_text(
            payload.get("full_name", payload.get("name")),
            "full_name",
            max_length=150,
        ),
    )
    email = collect(errors, lambda: as_email(payload.get("email")))
    password = collect(errors, lambda: as_password(payload.get("password")))
    birth_date = collect(
        errors, lambda: as_date(payload.get("birth_date"), "birth_date")
    )
    if birth_date is not None and birth_date > date.today():
        errors.append(
            FieldError("birth_date", "Must be today or earlier.", "out_of_range")
        )
    gender_value = collect(
        errors, lambda: as_choice(payload.get("gender"), "gender", Gender)
    )
    phone = collect(errors, lambda: as_phone(payload.get("phone")))
    if errors:
        raise ValidationError(errors)
    valid_full_name = cast(str, full_name)
    valid_email = cast(str, email)
    valid_password = cast(str, password)
    valid_birth_date = cast(date, birth_date)
    valid_gender = cast(str, gender_value)

    existing = db.session.scalar(select(User.user_id).where(User.email == valid_email))
    if existing is not None:
        raise ApiError(
            409, "email_exists", "An account with this email already exists."
        )

    user = User(
        email=valid_email,
        password_hash=bcrypt.generate(valid_password),
        role=UserRole.patient,
    )
    patient = Patient(
        user=user,
        full_name=valid_full_name,
        birth_date=valid_birth_date,
        gender=Gender(valid_gender),
        phone=phone,
    )
    db.session.add_all([user, patient])
    db.session.flush()
    write_audit("register", "user", user_id=user.user_id)

    response = jsonify(
        {
            "user_id": user.user_id,
            "patient_id": patient.patient_id,
            "email": user.email,
            "role": user.role.value,
            "user": serialize_user(user),
        }
    )
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            409, "email_exists", "An account with this email already exists."
        ) from exc
    return response, 201


@auth_bp.post("/login")
def login() -> tuple[Response, int]:
    """Authenticate an account and issue tokens."""
    payload = require_object(request.get_json(silent=True))
    email = as_email(payload.get("email"))
    password_value = as_text(
        payload.get("password"), "password", max_length=128, required=False
    )
    if password_value is None:
        raise ApiError(400, "bad_request", "A password is required.")
    password = password_value
    key = _attempt_key(email)

    if login_tracker.is_locked(key):
        raise _lock_error(key)

    user = db.session.scalar(
        select(User).where(User.email == email, User.is_active.is_(True))
    )
    if not _verify_password(password, user.password_hash if user else ""):
        login_tracker.record_failure(key)
        if user is not None:
            write_audit("login_failed", "auth", user_id=user.user_id)
            db.session.commit()
        if login_tracker.is_locked(key):
            raise _lock_error(key)
        raise ApiError(401, "login", "Invalid email or password.")

    active_user = cast(User, user)
    if bcrypt.needs_rehash(active_user.password_hash):
        active_user.password_hash = bcrypt.generate(password)
    login_tracker.reset(key)
    access_token, refresh_token = issue_tokens(active_user)
    write_audit("login", "auth", user_id=active_user.user_id)
    response = jsonify(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": _access_expires_in(),
            "user": serialize_user(active_user),
        }
    )
    set_refresh_cookies(response, refresh_token)
    db.session.commit()
    return response, 200


@auth_bp.post("/refresh")
def refresh() -> tuple[Response, int]:
    """Issue a new access token from the refresh cookie."""
    _verify_refresh_origin()
    verify_jwt_in_request(refresh=True, locations=["cookies"])
    user = _active_user_from_identity(get_jwt_identity())
    access_token = issue_access_token(str(user.user_id), claims_for(user))
    write_audit("token_refreshed", "auth", user_id=user.user_id)

    response = jsonify(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": _access_expires_in(),
            "user": serialize_user(user),
        }
    )
    db.session.commit()
    return response, 200


@auth_bp.post("/logout")
def logout() -> tuple[Response, int]:
    """Revoke the current access/refresh tokens and clear the refresh cookie."""
    _verify_refresh_origin()
    identity: object = None
    header_jwt = verify_jwt_in_request(optional=True, locations=["headers"])
    if header_jwt is not None:
        identity = get_jwt_identity()
        revoke_current_token()

    cookie_jwt = verify_jwt_in_request(
        optional=True, refresh=True, locations=["cookies"]
    )
    if cookie_jwt is not None:
        identity = get_jwt_identity()
        revoke_current_refresh_token()

    if identity is None:
        raise ApiError(401, "login", "Authentication is required.")

    user = _user_from_identity(identity, active_only=False)
    write_audit("logout", "auth", user_id=user.user_id)
    response = jsonify({"message": "Logged out."})
    unset_refresh_cookies(response)
    db.session.commit()
    return response, 200
