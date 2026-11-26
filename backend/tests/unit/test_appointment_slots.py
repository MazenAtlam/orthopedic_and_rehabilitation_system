from datetime import datetime, timedelta, timezone

import pytest

from app.fhir.writes import appointment_slot
from app.utils.common import ApiError


@pytest.mark.parametrize(
    ("start_offset", "end_offset", "overlap"),
    [(0, 30, True), (15, 45, True), (30, 60, False), (45, 75, False)],
)
def test_half_open_appointment_slots(start_offset, end_offset, overlap):
    start = datetime(2026, 11, 25, 10, tzinfo=timezone.utc)
    first = appointment_slot(start, start + timedelta(minutes=30))
    second = appointment_slot(
        start + timedelta(minutes=start_offset), start + timedelta(minutes=end_offset)
    )
    assert first.overlaps(second) is overlap


@pytest.mark.parametrize("end_offset", [0, -30])
def test_invalid_appointment_range_is_rejected(end_offset):
    start = datetime(2026, 11, 25, 10, tzinfo=timezone.utc)
    with pytest.raises(ApiError, match="end must be after start") as error:
        appointment_slot(start, start + timedelta(minutes=end_offset))
    assert error.value.status == 422
