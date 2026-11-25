"""F01 authentication and audit-flow integration tests."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import select

from app.extensions import db
from app.models import AuditLog
from tests.f01_f08.conftest import SeedData, assert_error, auth_headers, login


def registration(**overrides: Any) -> dict[str, Any]:
    """Build a valid patient registration payload."""
    payload: dict[str, Any] = {
        "full_name": "New Patient",
        "email": "new.patient@hcis.test",
        "password": "Test@12345",
        "birth_date": (date.today() - timedelta(days=365 * 30)).isoformat(),
        "gender": "female",
        "phone": "+15551234567",
    }
    payload.update(overrides)
    return payload


def test_register_creates_patient_account(client: FlaskClient) -> None:
    response = client.post("/api/v1/auth/register", json=registration())
    assert response.status_code == 201, response.get_json()
    body = response.get_json()
    assert body["role"] == "patient"
    assert body["email"] == "new.patient@hcis.test"
    assert isinstance(body["patient_id"], int)
    assert body["user"]["full_name"] == "New Patient"
    assert body["user"]["email"] == "new.patient@hcis.test"

    profile = client.get(
        f"/api/v1/patients/{body['patient_id']}",
        headers=auth_headers(client, "new.patient@hcis.test"),
    )
    assert profile.status_code == 200, profile.get_json()
    assert profile.get_json()["full_name"] == "New Patient"


def test_register_allows_missing_phone(client: FlaskClient) -> None:
    response = client.post("/api/v1/auth/register", json=registration(phone=None))
    assert response.status_code == 201, response.get_json()
    profile = client.get(
        f"/api/v1/patients/{response.get_json()['patient_id']}",
        headers=auth_headers(client, "new.patient@hcis.test"),
    )
    assert profile.status_code == 200, profile.get_json()
    assert profile.get_json()["phone"] is None


def test_register_rejects_duplicate_email(client: FlaskClient) -> None:
    first = client.post("/api/v1/auth/register", json=registration())
    assert first.status_code == 201
    duplicate = client.post("/api/v1/auth/register", json=registration())
    assert_error(duplicate, 409, "email_exists")


def test_register_collects_field_errors(client: FlaskClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json=registration(birth_date="2999-01-01", gender="alien", phone="abc"),
    )
    body = assert_error(response, 422, "validation_failed")
    fields = {item["field"] for item in body["error"]["details"]}
    assert {"birth_date", "gender", "phone"}.issubset(fields)


def test_login_returns_access_token_and_refresh_cookie(
    client: FlaskClient, seed: SeedData
) -> None:
    response = login(client, seed.patient1_email)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] > 0
    assert isinstance(body["access_token"], str)
    assert body["user"]["user_id"] == seed.patient1_user_id
    assert body["user"]["role"] == "patient"
    assert body["user"]["patient_id"] == seed.patient1_id
    assert body["user"]["full_name"] == "Patient One"
    assert client.get_cookie("refresh_token_cookie", path="/api/v1/auth") is not None


def test_five_failed_logins_then_temporary_block(
    client: FlaskClient, seed: SeedData
) -> None:
    for _ in range(4):
        assert_error(login(client, seed.patient1_email, "Wrong@12345"), 401, "login")

    locked = assert_error(
        login(client, seed.patient1_email, "Wrong@12345"), 429, "login_locked"
    )
    assert "Try again" in locked["error"]["message"]

    blocked = assert_error(login(client, seed.patient1_email), 429, "login_locked")
    assert blocked["error"]["code"] == "login_locked"


def test_refresh_issues_usable_access_token(
    client: FlaskClient, seed: SeedData
) -> None:
    first = login(client, seed.patient1_email)
    assert first.status_code == 200

    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["token_type"] == "Bearer"
    assert body["user"]["user_id"] == seed.patient1_user_id
    header = {"Authorization": f"Bearer {body['access_token']}"}
    profile = client.get(f"/api/v1/patients/{seed.patient1_id}", headers=header)
    assert profile.status_code == 200, profile.get_json()


def test_refresh_rejects_cross_site_origin(client: FlaskClient, seed: SeedData) -> None:
    assert login(client, seed.patient1_email).status_code == 200
    response = client.post(
        "/api/v1/auth/refresh", headers={"Origin": "https://evil.example"}
    )
    assert_error(response, 403, "forbidden")
    assert_error(
        client.post("/api/v1/auth/refresh", headers={"Origin": "null"}),
        403,
        "forbidden",
    )
    assert_error(
        client.post(
            "/api/v1/auth/refresh", headers={"Origin": "http://localhost:9999"}
        ),
        403,
        "forbidden",
    )


def test_logout_clears_refresh_cookie(client: FlaskClient, seed: SeedData) -> None:
    assert login(client, seed.patient1_email).status_code == 200
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["message"] == "Logged out."
    assert_error(client.post("/api/v1/auth/refresh"), 401, "login")


def test_login_missing_password_returns_400(client: FlaskClient) -> None:
    response = client.post("/api/v1/auth/login", json={"email": "nobody@hcis.test"})
    assert_error(response, 400, "bad_request")


def test_auth_events_are_audited(
    app: Flask, client: FlaskClient, seed: SeedData
) -> None:
    assert login(client, seed.patient1_email).status_code == 200
    assert client.post("/api/v1/auth/refresh").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 200

    actions = set(db.session.scalars(select(AuditLog.action)).all())
    assert {"login", "token_refreshed", "logout"}.issubset(actions)
