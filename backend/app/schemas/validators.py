"""Reusable request validation helpers for the F01-F08 endpoints."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Callable, NoReturn, TypeVar

from app.errors import ApiError, FieldError

MAX_ID = 2_147_483_647
_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,63}$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}")
_PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9\s\-()]{6,19}$")
MAX_BCRYPT_BYTES = 72


class ValidationError(ApiError):
    """Raised when one or more request fields fail validation."""

    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__(
            422,
            "validation_failed",
            "The request failed validation.",
            [error.as_dict() for error in errors],
        )
        self.errors = errors


T = TypeVar("T")


def collect(errors: list[FieldError], validate: Callable[[], T]) -> T | None:
    """Run a validator, accumulating field errors instead of raising them."""
    try:
        return validate()
    except ValidationError as exc:
        errors.extend(exc.errors)
        return None


def _invalid(field: str, message: str, code: str = "invalid") -> NoReturn:
    raise ValidationError([FieldError(field=field, message=message, code=code)])


def require_object(payload: object, field: str = "body") -> dict[str, Any]:
    """Return a JSON object payload or raise a 422 validation error."""
    if not isinstance(payload, dict):
        _invalid(field, "Must be a JSON object.", "not_object")
    return payload


def _missing_or_optional(field: str, required: bool) -> None:
    if required:
        _invalid(field, "This field is required.", "required")


def as_int(
    value: object,
    field: str,
    *,
    minimum: int = 1,
    maximum: int = MAX_ID,
    required: bool = True,
) -> int | None:
    """Validate an integer identifier supplied as an int or decimal string."""
    if value is None:
        _missing_or_optional(field, required)
        return None
    if isinstance(value, bool):
        _invalid(field, "Must be an integer.")
    if isinstance(value, int):
        candidate = value
    elif (
        isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and len(value) <= 10
    ):
        candidate = int(value)
    else:
        _invalid(field, "Must be an integer.")
    if not minimum <= candidate <= maximum:
        _invalid(field, f"Must be between {minimum} and {maximum}.", "out_of_range")
    return candidate


def as_text(
    value: object,
    field: str,
    *,
    max_length: int,
    required: bool = True,
    min_length: int = 1,
) -> str | None:
    """Validate trimmed text without NUL characters."""
    if value is None:
        _missing_or_optional(field, required)
        return None
    if not isinstance(value, str):
        _invalid(field, "Must be a string.")
    cleaned = value.strip()
    if not cleaned:
        if required:
            _invalid(field, "Must not be empty.")
        return None
    if "\x00" in cleaned:
        _invalid(field, "Must not contain NUL characters.")
    if len(cleaned) < min_length or len(cleaned) > max_length:
        _invalid(
            field,
            f"Must contain between {min_length} and {max_length} characters.",
            "length",
        )
    return cleaned


def as_email(value: object, field: str = "email") -> str:
    """Validate and normalise an email address."""
    email = as_text(value, field, max_length=255)
    if email is None or not _EMAIL_PATTERN.fullmatch(email):
        _invalid(field, "Must be a valid email address.", "format")
    return email.lower()


def as_password(value: object, field: str = "password") -> str:
    """Validate a plaintext password before hashing."""
    password = as_text(value, field, max_length=128, min_length=8)
    if password is None:
        _invalid(field, "Must be a valid password.")
    if len(password.encode("utf-8")) > MAX_BCRYPT_BYTES:
        _invalid(field, "Must be at most 72 bytes when encoded as UTF-8.", "length")
    return password


def as_date(
    value: object,
    field: str,
    *,
    required: bool = True,
    min_year: int = 1900,
    max_year: int = 2200,
) -> date | None:
    """Validate a strict ``YYYY-MM-DD`` calendar date."""
    if value is None:
        _missing_or_optional(field, required)
        return None
    if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
        _invalid(field, "Must be a date in YYYY-MM-DD format.", "format")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        _invalid(field, "Must be a real calendar date.", "format")
    if not min_year <= parsed.year <= max_year:
        _invalid(field, f"Year must be between {min_year} and {max_year}.", "range")
    return parsed


def as_datetime(
    value: object,
    field: str,
    *,
    required: bool = True,
    min_year: int = 1900,
    max_year: int = 2200,
) -> datetime | None:
    """Validate an ISO-8601 timestamp and normalise it to UTC.

    Values without an explicit offset are interpreted as UTC. ``Z`` suffixes
    are accepted and converted to a timezone-aware UTC ``datetime``.
    """
    if value is None:
        _missing_or_optional(field, required)
        return None
    if not isinstance(value, str):
        _invalid(field, "Must be an ISO-8601 date and time.", "format")
    candidate = value.strip()
    if candidate.endswith(("Z", "z")):
        candidate = f"{candidate[:-1]}+00:00"
    if not _DATETIME_PATTERN.match(candidate):
        _invalid(field, "Must include a time in ISO-8601 format.", "format")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        _invalid(field, "Must be an ISO-8601 date and time.", "format")
    if not min_year <= parsed.year <= max_year:
        _invalid(field, f"Year must be between {min_year} and {max_year}.", "range")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def as_decimal(
    value: object,
    field: str,
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
    places: int = 2,
    required: bool = True,
) -> Decimal | None:
    """Validate a finite decimal with a bounded number of fractional places."""
    if value is None:
        _missing_or_optional(field, required)
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        _invalid(field, "Must be a number.")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        _invalid(field, "Must be a number.", "format")
    if not parsed.is_finite():
        _invalid(field, "Must be a finite number.")
    exponent = parsed.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -places:
        _invalid(field, f"Must have at most {places} decimal places.", "precision")
    if minimum is not None and parsed < minimum:
        _invalid(field, f"Must be at least {minimum}.", "out_of_range")
    if maximum is not None and parsed > maximum:
        _invalid(field, f"Must be at most {maximum}.", "out_of_range")
    return parsed


def as_choice(
    value: object,
    field: str,
    allowed: tuple[str, ...] | type[Enum],
    *,
    required: bool = True,
) -> str | None:
    """Validate a value against a tuple of strings or an enum class."""
    if value is None:
        _missing_or_optional(field, required)
        return None
    if isinstance(allowed, type) and issubclass(allowed, Enum):
        accepted = tuple(str(item.value) for item in allowed)
    else:
        accepted = tuple(allowed)
    candidate = value.value if isinstance(value, Enum) else value
    if not isinstance(candidate, str) or candidate not in accepted:
        _invalid(field, f"Must be one of: {', '.join(accepted)}.", "choice")
    return candidate


def as_bool(value: object, field: str, *, required: bool = True) -> bool | None:
    """Validate a JSON boolean."""
    if value is None:
        _missing_or_optional(field, required)
        return None
    if not isinstance(value, bool):
        _invalid(field, "Must be a boolean.")
    return value


def as_query_bool(value: object, field: str, *, required: bool = True) -> bool | None:
    """Validate a boolean supplied as a query-string value."""
    if value is None:
        _missing_or_optional(field, required)
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes"}:
            return True
        if normalized in {"0", "false", "no"}:
            return False
    _invalid(field, "Must be true or false.")


def as_phone(
    value: object, field: str = "phone", *, required: bool = False
) -> str | None:
    """Validate an optional contact phone number."""
    phone = as_text(value, field, max_length=20, required=required)
    if phone is None:
        return None
    if not _PHONE_PATTERN.fullmatch(phone):
        _invalid(field, "Must contain digits only, with optional separators.", "format")
    digit_count = sum(character.isdigit() for character in phone)
    if not 7 <= digit_count <= 15:
        _invalid(field, "Must contain between 7 and 15 digits.", "format")
    return phone


def like_pattern(value: str) -> str:
    """Return a substring pattern with SQL ``LIKE`` wildcards escaped."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def pagination(
    params: Mapping[str, object],
    *,
    default_page_size: int = 25,
    max_page_size: int = 100,
) -> tuple[int, int]:
    """Extract validated ``page`` and ``page_size`` values from query parameters."""
    page = as_int(params.get("page"), "page", required=False)
    page_size = as_int(
        params.get("page_size"),
        "page_size",
        maximum=max_page_size,
        required=False,
    )
    return page or 1, page_size or default_page_size
