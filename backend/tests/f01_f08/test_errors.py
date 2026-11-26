"""Standard JSON error-envelope and health endpoint tests for the Phase 2 API."""

from __future__ import annotations

from datetime import date

from flask.testing import FlaskClient

from tests.f01_f08.conftest import SeedData, assert_error, auth_headers


def test_health_endpoints(client: FlaskClient) -> None:
    for path in ("/api/v1/health", "/healthz"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.get_json() == {"status": "ok"}


def test_400_bad_request(client: FlaskClient) -> None:
    response = client.post("/api/v1/auth/login", json={"email": "nobody@hcis.test"})
    body = assert_error(response, 400, "bad_request")
    assert set(body["error"]) == {"code", "message"}


def test_401_unauthorized(client: FlaskClient) -> None:
    body = assert_error(client.get("/api/v1/appointments"), 401, "login")
    assert set(body["error"]) == {"code", "message"}


def test_403_forbidden(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.patient1_email)
    assert_error(client.get("/api/v1/patients", headers=headers), 403, "forbidden")


def test_404_not_found(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.doctor_email)
    body = assert_error(
        client.get("/api/v1/records/999999", headers=headers), 404, "not_found"
    )
    assert set(body["error"]) == {"code", "message"}


def test_409_conflict(client: FlaskClient, seed: SeedData) -> None:
    payload = {
        "full_name": "Duplicate Patient",
        "email": seed.patient1_email,
        "password": "Test@12345",
        "birth_date": date(1990, 1, 1).isoformat(),
        "gender": "male",
        "phone": "+15550000000",
    }
    assert_error(
        client.post("/api/v1/auth/register", json=payload), 409, "email_exists"
    )


def test_422_validation_failed(client: FlaskClient) -> None:
    payload = {
        "full_name": "Bad Patient",
        "email": "bad@hcis.test",
        "password": "Test@12345",
        "birth_date": "not-a-date",
        "gender": "unknown",
        "phone": "abc",
    }
    body = assert_error(
        client.post("/api/v1/auth/register", json=payload),
        422,
        "validation_failed",
    )
    assert isinstance(body["error"]["details"], list)
    assert all(
        {"field", "message", "code"}.issubset(item) for item in body["error"]["details"]
    )


def test_error_responses_echo_request_id(client: FlaskClient) -> None:
    response = client.get(
        "/api/v1/appointments", headers={"X-Request-ID": "step5-error-check"}
    )
    assert_error(response, 401, "login")
    assert response.headers["X-Request-ID"] == "step5-error-check"
