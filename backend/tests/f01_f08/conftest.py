"""Shared fixtures for the Phase 2 F01-F08 test suite."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, cast

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.dialects.postgresql import ExcludeConstraint

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module  # noqa: E402
from app.extensions import bcrypt, db, login_tracker, token_denylist  # noqa: E402
from app.models import (  # noqa: E402
    Appointment,
    AppointmentStatus,
    AppointmentType,
    Base,
    Gender,
    Icd10Code,
    Patient,
    Staff,
    StaffType,
    User,
    UserRole,
)

PASSWORD = "Test@12345"
CLINIC_DAY = date.today() + timedelta(days=1)
ICD10_CODE = "M17.9"


def utc_at(hour: int, minute: int = 0, *, day: date = CLINIC_DAY) -> datetime:
    """Build a timezone-aware UTC time for the seeded clinic day."""
    return datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)


def iso_at(hour: int, minute: int = 0, *, day: date = CLINIC_DAY) -> str:
    """Build an ISO-8601 UTC string for the seeded clinic day."""
    return utc_at(hour, minute, day=day).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class SeedData:
    """Identifiers and credentials shared by integration tests."""

    admin_email: str
    doctor_email: str
    physio_email: str
    patient1_email: str
    patient2_email: str
    admin_user_id: int
    doctor_user_id: int
    physio_user_id: int
    patient1_user_id: int
    patient2_user_id: int
    doctor_id: int
    physio_id: int
    patient1_id: int
    patient2_id: int
    appointment_id: int
    password: str = PASSWORD


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Iterator[Flask]:
    """Create an isolated in-memory SQLite application with seeded schema."""
    monkeypatch.setattr(app_module, "validate_config", lambda config: None)
    login_tracker.clear()
    token_denylist.clear()

    appointment_table = Base.metadata.tables["appointment"]
    saved_constraints = set(appointment_table.constraints)
    appointment_table.constraints = {
        constraint
        for constraint in saved_constraints
        if not isinstance(constraint, ExcludeConstraint)
    }

    application = app_module.create_app(
        "testing",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_ENGINE_OPTIONS={},
        JWT_SECRET_KEY="k" * 40,
        JWT_COOKIE_SECURE=False,
        BCRYPT_ROUNDS=4,
        RATELIMIT_ENABLED=False,
        LOGIN_MAX_ATTEMPTS=5,
        LOGIN_LOCK_MINUTES=15,
        LOGIN_ATTEMPT_WINDOW_MINUTES=15,
    )
    with application.app_context():
        try:
            db.create_all()
            yield application
        finally:
            db.session.remove()
            db.drop_all()
            appointment_table.constraints = saved_constraints


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Return a test client bound to the isolated application."""
    return app.test_client()


@pytest.fixture
def seed(app: Flask) -> SeedData:
    """Seed one admin, two clinicians, two patients and a booked slot."""
    users = [
        User(
            email="admin@hcis.test",
            password_hash=bcrypt.generate(PASSWORD),
            role=UserRole.admin,
            is_active=True,
        ),
        User(
            email="doctor1@hcis.test",
            password_hash=bcrypt.generate(PASSWORD),
            role=UserRole.staff,
            is_active=True,
        ),
        User(
            email="physio1@hcis.test",
            password_hash=bcrypt.generate(PASSWORD),
            role=UserRole.staff,
            is_active=True,
        ),
        User(
            email="patient1@hcis.test",
            password_hash=bcrypt.generate(PASSWORD),
            role=UserRole.patient,
            is_active=True,
        ),
        User(
            email="patient2@hcis.test",
            password_hash=bcrypt.generate(PASSWORD),
            role=UserRole.patient,
            is_active=True,
        ),
    ]
    db.session.add_all(users)
    db.session.flush()

    doctor = Staff(
        user_id=users[1].user_id,
        full_name="Doctor One",
        staff_type=StaffType.doctor,
        specialty="orthopedics",
    )
    physio = Staff(
        user_id=users[2].user_id,
        full_name="Physio One",
        staff_type=StaffType.physiotherapist,
        specialty="rehabilitation",
    )
    db.session.add_all([doctor, physio])
    db.session.flush()

    patients = [
        Patient(
            user_id=users[3].user_id,
            full_name="Patient One",
            birth_date=date(1990, 1, 1),
            gender=Gender.male,
            phone="+12345678901",
        ),
        Patient(
            user_id=users[4].user_id,
            full_name="Patient Two",
            birth_date=date(1991, 2, 2),
            gender=Gender.female,
            phone="+12345678902",
        ),
    ]
    db.session.add_all(patients)
    db.session.flush()

    db.session.add(
        Icd10Code(
            code=ICD10_CODE,
            description="Osteoarthritis of knee, unspecified",
            category="Diseases of the musculoskeletal system",
        )
    )
    db.session.add(
        Icd10Code(
            code="M25.5",
            description="Pain in joint",
            category="Diseases of the musculoskeletal system",
        )
    )

    appointment = Appointment(
        patient_id=patients[0].patient_id,
        staff_id=doctor.staff_id,
        type=AppointmentType.consultation,
        start_time=utc_at(10),
        end_time=utc_at(10, 30),
        status=AppointmentStatus.booked,
    )
    db.session.add(appointment)
    db.session.commit()

    return SeedData(
        admin_email=users[0].email,
        doctor_email=users[1].email,
        physio_email=users[2].email,
        patient1_email=users[3].email,
        patient2_email=users[4].email,
        admin_user_id=users[0].user_id,
        doctor_user_id=users[1].user_id,
        physio_user_id=users[2].user_id,
        patient1_user_id=users[3].user_id,
        patient2_user_id=users[4].user_id,
        doctor_id=doctor.staff_id,
        physio_id=physio.staff_id,
        patient1_id=patients[0].patient_id,
        patient2_id=patients[1].patient_id,
        appointment_id=appointment.appointment_id,
    )


def login(client: FlaskClient, email: str, password: str = PASSWORD) -> Any:
    """POST a login and return the raw test-client response."""
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


def auth_headers(
    client: FlaskClient, email: str, password: str = PASSWORD
) -> dict[str, str]:
    """Log in and return an Authorization header for the access token."""
    response = login(client, email, password)
    assert response.status_code == 200, response.get_json()
    return {"Authorization": f"Bearer {response.get_json()['access_token']}"}


def assert_error(response: Any, status: int, code: str) -> dict[str, Any]:
    """Assert the shared error envelope and return the response body."""
    assert response.status_code == status, response.get_json()
    body = cast(dict[str, Any], response.get_json())
    assert "error" in body
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    return body
