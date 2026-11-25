"""Role-based access control primitives shared by F01-F08."""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, TypeVar, cast

from flask import g

from app.errors import ApiError
from app.models import StaffType, UserRole

F = TypeVar("F", bound=Callable[..., Any])


@dataclass(frozen=True, slots=True)
class Actor:
    """Authenticated identity loaded from the database for each request."""

    user_id: int
    role: UserRole
    patient_id: int | None = None
    staff_id: int | None = None
    staff_type: StaffType | None = None

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.admin

    @property
    def is_staff(self) -> bool:
        return self.role is UserRole.staff and self.staff_id is not None

    @property
    def is_patient(self) -> bool:
        return self.role is UserRole.patient and self.patient_id is not None


def current_actor() -> Actor:
    """Return the request actor or raise a 401 error when authentication is absent."""
    actor = getattr(g, "actor", None)
    if not isinstance(actor, Actor):
        raise ApiError(401, "login", "Authentication is required.")
    return actor


def require_roles(*roles: UserRole) -> Callable[[F], F]:
    """Require the request actor to hold one of ``roles``."""
    allowed = frozenset(roles)

    def decorate(handler: F) -> F:
        @wraps(handler)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            actor = current_actor()
            if actor.role not in allowed:
                raise ApiError(
                    403, "forbidden", "Your role cannot perform this action."
                )
            return handler(*args, **kwargs)

        return cast(F, wrapped)

    return decorate


def require_staff(*types: StaffType) -> Callable[[F], F]:
    """Require a staff actor, optionally limited to specific staff types."""
    allowed = frozenset(types)

    def decorate(handler: F) -> F:
        @wraps(handler)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            actor = current_actor()
            if not actor.is_staff:
                raise ApiError(403, "forbidden", "Staff access is required.")
            if allowed and (
                actor.staff_type is None or actor.staff_type not in allowed
            ):
                raise ApiError(
                    403, "forbidden", "Your staff type cannot perform this action."
                )
            return handler(*args, **kwargs)

        return cast(F, wrapped)

    return decorate


def require_admin_or_staff() -> Callable[[F], F]:
    """Require an administrator or a clinical staff member."""

    def decorate(handler: F) -> F:
        @wraps(handler)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            actor = current_actor()
            if not (actor.is_admin or actor.is_staff):
                raise ApiError(403, "forbidden", "Admin or staff access is required.")
            return handler(*args, **kwargs)

        return cast(F, wrapped)

    return decorate


def require_patient_or_staff() -> Callable[[F], F]:
    """Require an owning patient or a clinical staff member."""

    def decorate(handler: F) -> F:
        @wraps(handler)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            actor = current_actor()
            if not (actor.is_patient or actor.is_staff):
                raise ApiError(403, "forbidden", "Patient or staff access is required.")
            return handler(*args, **kwargs)

        return cast(F, wrapped)

    return decorate


def require_patient_access(
    patient_id: int, *, allow_staff: bool = True, allow_admin: bool = False
) -> None:
    """Allow the owning patient and optionally staff access to a patient resource."""
    actor = current_actor()
    if actor.is_patient and actor.patient_id == patient_id:
        return
    if allow_staff and actor.is_staff:
        return
    if allow_admin and actor.is_admin:
        return
    raise ApiError(403, "forbidden", "You cannot access this patient's data.")


def require_patient_owner(arg_name: str = "patient_id") -> Callable[[F], F]:
    """Require a patient actor to own the patient id in the view arguments."""

    def decorate(handler: F) -> F:
        @wraps(handler)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            actor = current_actor()
            try:
                patient_id = int(kwargs[arg_name])
            except (KeyError, TypeError, ValueError) as exc:
                raise ApiError(
                    400, "bad_request", "A patient identifier is required."
                ) from exc
            if not actor.is_patient or actor.patient_id != patient_id:
                raise ApiError(
                    403, "forbidden", "You can only access your own patient data."
                )
            return handler(*args, **kwargs)

        return cast(F, wrapped)

    return decorate


def can_read_record(patient_id: int) -> bool:
    """Report whether the actor may read clinical records for ``patient_id``.

    Administrators are deliberately excluded from medical records by the RBAC
    matrix: they manage accounts, services and reports, not clinical notes.
    """
    actor = current_actor()
    if actor.is_patient:
        return actor.patient_id == patient_id
    return actor.is_staff


require_admin = require_roles(UserRole.admin)
require_patient = require_roles(UserRole.patient)
require_clinical_staff = require_staff
require_ownership = require_patient_owner
