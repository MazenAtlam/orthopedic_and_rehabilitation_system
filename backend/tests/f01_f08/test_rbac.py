"""RBAC and patient-ownership tests across F01-F08 and B1."""

from __future__ import annotations

from datetime import date, timedelta

from flask.testing import FlaskClient

from tests.f01_f08.conftest import SeedData, assert_error, auth_headers, iso_at


def test_icd10_lookup_allows_admin_and_staff_but_denies_patient(
    client: FlaskClient, seed: SeedData
) -> None:
    for email in (seed.admin_email, seed.doctor_email):
        response = client.get(
            "/api/v1/icd10?q=knee", headers=auth_headers(client, email)
        )
        assert response.status_code == 200, response.get_json()

    patient_headers = auth_headers(client, seed.patient1_email)
    assert_error(
        client.get("/api/v1/icd10?q=knee", headers=patient_headers), 403, "forbidden"
    )


def test_unauthenticated_request_returns_401(client: FlaskClient) -> None:
    assert_error(client.get("/api/v1/appointments"), 401, "login")


def test_patient_profile_ownership(client: FlaskClient, seed: SeedData) -> None:
    own = auth_headers(client, seed.patient1_email)
    other = auth_headers(client, seed.patient2_email)

    assert (
        client.get(f"/api/v1/patients/{seed.patient1_id}", headers=own).status_code
        == 200
    )
    assert_error(
        client.get(f"/api/v1/patients/{seed.patient1_id}", headers=other),
        403,
        "forbidden",
    )
    assert_error(client.get("/api/v1/patients", headers=own), 403, "forbidden")


def test_patient_cannot_use_clinical_write_routes(
    client: FlaskClient, seed: SeedData
) -> None:
    headers = auth_headers(client, seed.patient1_email)
    record_payload = {
        "patient_id": seed.patient1_id,
        "chief_complaint": "Knee pain",
        "icd10_code": "M17.9",
    }
    plan_payload = {
        "patient_id": seed.patient1_id,
        "title": "Knee rehabilitation",
        "start_date": date.today().isoformat(),
    }

    assert_error(
        client.post("/api/v1/records", headers=headers, json=record_payload),
        403,
        "forbidden",
    )
    assert_error(
        client.post("/api/v1/treatment-plans", headers=headers, json=plan_payload),
        403,
        "forbidden",
    )


def test_admin_has_no_clinical_access(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.admin_email)
    assert_error(
        client.get("/api/v1/treatment-plans", headers=headers), 403, "forbidden"
    )
    assert_error(
        client.get("/api/v1/records/999999", headers=headers), 403, "forbidden"
    )


def test_admin_can_manage_appointments(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.admin_email)
    payload = {
        "patient_id": seed.patient1_id,
        "staff_id": seed.doctor_id,
        "type": "consultation",
        "start_time": iso_at(11),
        "end_time": iso_at(11, 30),
    }

    created = client.post("/api/v1/appointments", headers=headers, json=payload)
    assert created.status_code == 201, created.get_json()
    appointment_id = created.get_json()["appointment_id"]

    updated = client.patch(
        f"/api/v1/appointments/{appointment_id}",
        headers=headers,
        json={"status": "completed"},
    )
    assert updated.status_code == 200, updated.get_json()
    assert updated.get_json()["status"] == "completed"

    cancelled = client.delete(f"/api/v1/appointments/{appointment_id}", headers=headers)
    assert cancelled.status_code == 200, cancelled.get_json()
    assert cancelled.get_json()["status"] == "cancelled"


def test_patient_ownership_for_appointments(
    client: FlaskClient, seed: SeedData
) -> None:
    other = auth_headers(client, seed.patient2_email)
    booking = {
        "patient_id": seed.patient1_id,
        "staff_id": seed.doctor_id,
        "type": "consultation",
        "start_time": iso_at(11),
        "end_time": iso_at(11, 30),
    }

    assert_error(
        client.post("/api/v1/appointments", headers=other, json=booking),
        403,
        "forbidden",
    )
    assert_error(
        client.patch(
            f"/api/v1/appointments/{seed.appointment_id}",
            headers=other,
            json={"status": "cancelled"},
        ),
        403,
        "forbidden",
    )
    assert_error(
        client.delete(f"/api/v1/appointments/{seed.appointment_id}", headers=other),
        403,
        "forbidden",
    )
    assert_error(
        client.get(f"/api/v1/appointments?patient={seed.patient1_id}", headers=other),
        403,
        "forbidden",
    )


def test_patient_ownership_for_clinical_data(
    client: FlaskClient, seed: SeedData
) -> None:
    doctor_headers = auth_headers(client, seed.doctor_email)
    physio_headers = auth_headers(client, seed.physio_email)
    other_headers = auth_headers(client, seed.patient2_email)

    record_response = client.post(
        "/api/v1/records",
        headers=doctor_headers,
        json={
            "patient_id": seed.patient1_id,
            "visit_date": date.today().isoformat(),
            "diagnosis": "Knee osteoarthritis",
            "icd10_code": "M17.9",
        },
    )
    assert record_response.status_code == 201, record_response.get_json()
    record_id = record_response.get_json()["record_id"]

    plan_response = client.post(
        "/api/v1/treatment-plans",
        headers=physio_headers,
        json={
            "patient_id": seed.patient1_id,
            "title": "Knee rehabilitation",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=30)).isoformat(),
        },
    )
    assert plan_response.status_code == 201, plan_response.get_json()
    plan_id = plan_response.get_json()["plan_id"]

    assert_error(
        client.get(f"/api/v1/records/{record_id}", headers=other_headers),
        403,
        "forbidden",
    )
    assert_error(
        client.get(
            f"/api/v1/patients/{seed.patient1_id}/records", headers=other_headers
        ),
        403,
        "forbidden",
    )
    assert_error(
        client.get(
            f"/api/v1/patients/{seed.patient1_id}/prescriptions",
            headers=other_headers,
        ),
        403,
        "forbidden",
    )
    assert_error(
        client.get(
            f"/api/v1/treatment-plans/{plan_id}/sessions", headers=other_headers
        ),
        403,
        "forbidden",
    )


def test_staff_can_read_any_patient_clinical_data(
    client: FlaskClient, seed: SeedData
) -> None:
    headers = auth_headers(client, seed.doctor_email)
    for patient_id in (seed.patient1_id, seed.patient2_id):
        history = client.get(f"/api/v1/patients/{patient_id}/records", headers=headers)
        prescriptions = client.get(
            f"/api/v1/patients/{patient_id}/prescriptions", headers=headers
        )
        assert history.status_code == 200, history.get_json()
        assert prescriptions.status_code == 200, prescriptions.get_json()
