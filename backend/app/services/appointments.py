"""Pure appointment interval helpers shared by F04 availability and F05 booking."""

from __future__ import annotations

from datetime import datetime, timezone


def utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime, treating naive values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    """Render a datetime as an ISO-8601 UTC string with a ``Z`` suffix."""
    return utc(value).isoformat().replace("+00:00", "Z")


def times_overlap(
    start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime
) -> bool:
    """Report whether two half-open intervals ``[start, end)`` overlap.

    Back-to-back slots that touch at one boundary do not overlap. Invalid or
    empty intervals never overlap.
    """
    a_start, a_end = utc(start_a), utc(end_a)
    b_start, b_end = utc(start_b), utc(end_b)
    if a_end <= a_start or b_end <= b_start:
        return False
    return a_start < b_end and b_start < a_end


appointments_overlap = times_overlap
