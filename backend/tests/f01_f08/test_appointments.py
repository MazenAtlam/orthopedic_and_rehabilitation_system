"""F05 appointment unit and integration tests."""

from __future__ import annotations

from typing import Any

from flask.testing import FlaskClient
from sqlalchemy import func, select

from app.extensions import db
from app.models import Appointment, AppointmentStatus, AuditLog
from app.services import times_overlap
from tests.f01_f08.conftest import (
    CLINIC_DAY,
    SeedData,
    assert_error,
    auth_headers,
    iso_at,
    utc_at,
)


def booking(
    seed: SeedData,
    start_hour: int,
    end_hour: int,
    *,
    start_minute: int = 0,
    end_minute: int = 0,
    patient_id: int | None = None,
) -> dict[str, Any]:
    """Build a booking payload for the seeded clinic day."""
    return {
        "patient_id": patient_id or seed.patient1_id,
        "staff_id": seed.doctor_id,
        "type": "consultation",
        "start_time": iso_at(start_hour, start_minute),
        "end_time": iso_at(end_hour, end_minute),
        "notes": "Smoke-test note",
    }


def test_times_overlap_uses_half_open_intervals() -> None:
    """Pure unit coverage matching appointment-overlap acceptance criteria."""
    start = utc_at(10)
    end = utc_at(10, 30)
    assert times_overlap(start, end, start, end)
    assert times_overlap(start, end, utc_at(10, 15), utc_at(10, 45))
    assert not times_overlap(start, end, utc_at(10, 30), utc_at(11))
    assert not times_overlap(start, end, utc_at(11), utc_at(11, 30))
    assert not times_overlap(end, start, start, end)


def test_availability_hides_booked_slot(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.patient1_email)
    response = client.get(
        f"/api/v1/staff/{seed.doctor_id}/availability?date={CLINIC_DAY.isoformat()}",
        headers=headers,
    )
    assert response.status_code == 200, response.get_json()
    slots = response.get_json()
    starts = {slot[11:16] for slot in slots}
    assert len(slots) == 19
    assert "10:00" not in starts
    assert "10:30" in starts


def test_booking_touching_slot_is_allowed(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.patient1_email)
    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=booking(seed, 10, 11, start_minute=30),
    )
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["status"] == "booked"
    assert response.get_json()["start_time"].endswith("10:30:00Z")


def test_overlapping_booking_returns_409(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.patient2_email)
    overlap = booking(
        seed, 10, 10, start_minute=15, end_minute=45, patient_id=seed.patient2_id
    )
    assert_error(
        client.post("/api/v1/appointments", headers=headers, json=overlap),
        409,
        "appointment_conflict",
    )
    duplicate = booking(seed, 10, 10, end_minute=30, patient_id=seed.patient1_id)
    assert_error(
        client.post(
            "/api/v1/appointments",
            headers=auth_headers(client, seed.patient1_email),
            json=duplicate,
        ),
        409,
        "appointment_conflict",
    )


def test_end_before_start_is_rejected(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.patient1_email)
    payload = booking(seed, 13, 12)
    body = assert_error(
        client.post("/api/v1/appointments", headers=headers, json=payload),
        422,
        "validation_failed",
    )
    assert any(item["field"] == "end_time" for item in body["error"]["details"])
    assert db.session.scalar(select(func.count()).select_from(Appointment)) == 1


def test_reschedule_checks_overlap(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.patient1_email)
    created = client.post(
        "/api/v1/appointments", headers=headers, json=booking(seed, 11, 12)
    )
    assert created.status_code == 201, created.get_json()
    appointment_id = created.get_json()["appointment_id"]

    conflict = {
        "start_time": iso_at(10, 15),
        "end_time": iso_at(10, 45),
    }
    assert_error(
        client.patch(
            f"/api/v1/appointments/{appointment_id}", headers=headers, json=conflict
        ),
        409,
        "appointment_conflict",
    )

    free = {"start_time": iso_at(12), "end_time": iso_at(12, 30)}
    response = client.patch(
        f"/api/v1/appointments/{appointment_id}", headers=headers, json=free
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["start_time"].endswith("12:00:00Z")


def test_cancel_soft_deletes_and_frees_slot(
    client: FlaskClient, seed: SeedData
) -> None:
    headers = auth_headers(client, seed.patient1_email)
    response = client.delete(
        f"/api/v1/appointments/{seed.appointment_id}", headers=headers
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["status"] == "cancelled"

    stored = db.session.get(Appointment, seed.appointment_id)
    assert stored is not None
    assert stored.status is AppointmentStatus.cancelled

    availability = client.get(
        f"/api/v1/staff/{seed.doctor_id}/availability?date={CLINIC_DAY.isoformat()}",
        headers=headers,
    )
    starts = {slot[11:16] for slot in availability.get_json()}
    assert "10:00" in starts


def test_status_change_rights(client: FlaskClient, seed: SeedData) -> None:
    patient_headers = auth_headers(client, seed.patient1_email)
    staff_headers = auth_headers(client, seed.doctor_email)

    denied = assert_error(
        client.patch(
            f"/api/v1/appointments/{seed.appointment_id}",
            headers=patient_headers,
            json={"status": "completed"},
        ),
        403,
        "forbidden",
    )
    assert denied["error"]["code"] == "forbidden"

    completed = client.patch(
        f"/api/v1/appointments/{seed.appointment_id}",
        headers=staff_headers,
        json={"status": "completed"},
    )
    assert completed.status_code == 200, completed.get_json()
    assert completed.get_json()["status"] == "completed"


def test_appointment_lists_are_owner_scoped(
    client: FlaskClient, seed: SeedData
) -> None:
    patient1 = client.get(
        "/api/v1/appointments", headers=auth_headers(client, seed.patient1_email)
    )
    patient2 = client.get(
        "/api/v1/appointments", headers=auth_headers(client, seed.patient2_email)
    )
    doctor = client.get(
        "/api/v1/appointments", headers=auth_headers(client, seed.doctor_email)
    )

    assert len(patient1.get_json()) == 1
    assert patient2.get_json() == []
    assert len(doctor.get_json()) == 1
    assert patient1.get_json()[0]["patient_name"] == "Patient One"
    assert patient1.get_json()[0]["staff_name"] == "Doctor One"


def test_appointment_mutations_are_audited(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.patient1_email)
    created = client.post(
        "/api/v1/appointments", headers=headers, json=booking(seed, 11, 12)
    )
    appointment_id = created.get_json()["appointment_id"]
    assert created.status_code == 201

    assert (
        client.patch(
            f"/api/v1/appointments/{appointment_id}",
            headers=headers,
            json={"start_time": iso_at(12), "end_time": iso_at(12, 30)},
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/v1/appointments/{appointment_id}", headers=headers
        ).status_code
        == 200
    )

    actions = set(db.session.scalars(select(AuditLog.action)).all())
    resources = set(db.session.scalars(select(AuditLog.resource)).all())
    assert {
        "appointment_created",
        "appointment_rescheduled",
        "appointment_cancelled",
    }.issubset(actions)
    assert "Smoke-test note" not in " ".join(resources)
