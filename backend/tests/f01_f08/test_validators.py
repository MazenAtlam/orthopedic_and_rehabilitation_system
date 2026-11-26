"""Pure unit tests for reusable request validators."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.errors import FieldError
from app.schemas import (
    ValidationError,
    as_bool,
    as_date,
    as_datetime,
    as_decimal,
    as_int,
    as_password,
    as_phone,
    as_query_bool,
    as_text,
    collect,
    like_pattern,
    pagination,
)


def error_fields(exc: ValidationError) -> set[str]:
    """Return the field names carried by a validation error."""
    return {error.field for error in exc.errors}


def test_as_int_accepts_decimal_strings_and_rejects_booleans() -> None:
    assert as_int("42", "id") == 42
    with pytest.raises(ValidationError) as exc:
        as_int(True, "id")
    assert error_fields(exc.value) == {"id"}


def test_as_text_trims_and_rejects_nul_characters() -> None:
    assert as_text("  patient  ", "name", max_length=20) == "patient"
    with pytest.raises(ValidationError):
        as_text("bad\x00name", "name", max_length=20)


def test_as_date_and_datetime_normalise_values() -> None:
    parsed = as_date("2026-02-28", "date")
    assert parsed is not None and parsed.isoformat() == "2026-02-28"
    with pytest.raises(ValidationError):
        as_date("2026-02-30", "date")

    aware = as_datetime("2026-02-28T10:00:00Z", "timestamp")
    naive = as_datetime("2026-02-28T10:00:00", "timestamp")
    assert aware == naive
    assert aware is not None and aware.tzinfo is timezone.utc
    assert isinstance(aware, datetime)
    with pytest.raises(ValidationError):
        as_datetime("2026-02-28", "timestamp")


def test_as_password_respects_bcrypt_byte_limit() -> None:
    assert as_password("abcdefgh")
    with pytest.raises(ValidationError):
        as_password("a" * 73)


def test_as_decimal_enforces_finite_values_and_precision() -> None:
    assert as_decimal("12.30", "value") == Decimal("12.30")
    with pytest.raises(ValidationError):
        as_decimal("NaN", "value")
    with pytest.raises(ValidationError):
        as_decimal("1.234", "value")


def test_boolean_and_phone_helpers() -> None:
    assert as_bool(False, "flag") is False
    assert as_query_bool("YES", "flag") is True
    assert as_query_bool("no", "flag") is False
    with pytest.raises(ValidationError):
        as_query_bool("maybe", "flag")
    assert as_phone("+1 (555) 123-4567") == "+1 (555) 123-4567"
    with pytest.raises(ValidationError):
        as_phone("abc")
    with pytest.raises(ValidationError):
        as_phone("1------")


def test_like_pattern_escapes_sql_wildcards() -> None:
    assert like_pattern("a%b_c") == "%a\\%b\\_c%"
    assert like_pattern("a\\b") == "%a\\\\b%"


def test_pagination_defaults_and_bounds() -> None:
    assert pagination({}) == (1, 25)
    assert pagination({"page": "2", "page_size": "10"}) == (2, 10)
    with pytest.raises(ValidationError):
        pagination({"page_size": "101"})


def test_collect_accumulates_multiple_field_errors() -> None:
    errors: list[FieldError] = []
    values = [
        collect(errors, lambda: as_int("x", "first")),
        collect(errors, lambda: as_phone("abc", "second")),
    ]
    assert values == [None, None]
    assert len(errors) == 2
    assert {error.field for error in errors} == {"first", "second"}
