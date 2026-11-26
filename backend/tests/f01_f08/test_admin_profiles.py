"""F03 user-management and F04 profile endpoint integration tests."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from flask.testing import FlaskClient

from tests.f01_f08.conftest import SeedData, assert_error, auth_headers


def test_admin_user_list_filters(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.admin_email)

    all_users = client.get("/api/v1/users", headers=headers)
    assert all_users.status_code == 200, all_users.get_json()
    assert len(all_users.get_json()) == 5

    staff = client.get("/api/v1/users?role=staff", headers=headers)
    assert len(staff.get_json()) == 2
    assert all(item["role"] == "staff" for item in staff.get_json())

    inactive = client.get("/api/v1/users?is_active=false", headers=headers)
    assert inactive.get_json() == []

    searched = client.get(f"/api/v1/users?q={seed.doctor_email}", headers=headers)
    assert len(searched.get_json()) == 1
    assert searched.get_json()[0]["user_id"] == seed.doctor_user_id

    wildcard = client.get("/api/v1/users?q=%", headers=headers)
    assert wildcard.get_json() == []


def test_admin_creates_and_updates_staff_account(
    client: FlaskClient, seed: SeedData
) -> None:
    headers = auth_headers(client, seed.admin_email)
    payload: dict[str, Any] = {
        "email": "nurse@hcis.test",
        "password": "Test@12345",
        "role": "staff",
        "full_name": "Nurse One",
        "staff_type": "nurse",
        "specialty": "rehabilitation",
    }

    created = client.post("/api/v1/users", headers=headers, json=payload)
    assert created.status_code == 201, created.get_json()
    user = created.get_json()
    assert user["role"] == "staff"
    assert user["staff_type"] == "nurse"
    assert user["full_name"] == "Nurse One"
    assert "password" not in user

    duplicate = client.post("/api/v1/users", headers=headers, json=payload)
    assert_error(duplicate, 409, "email_exists")

    invalid_role = client.post(
        "/api/v1/users", headers=headers, json=dict(payload, role="patient")
    )
    assert_error(invalid_role, 422, "validation_failed")

    updated = client.patch(
        f"/api/v1/users/{user['user_id']}",
        headers=headers,
        json={"is_active": False, "full_name": "Nurse Two"},
    )
    assert updated.status_code == 200, updated.get_json()
    assert updated.get_json()["is_active"] is False
    assert updated.get_json()["full_name"] == "Nurse Two"

    assert_error(
        client.patch("/api/v1/users/999999", headers=headers, json={"is_active": True}),
        404,
        "not_found",
    )


def test_staff_role_change_requires_a_profile(
    client: FlaskClient, seed: SeedData
) -> None:
    headers = auth_headers(client, seed.admin_email)

    missing_profile = client.patch(
        f"/api/v1/users/{seed.patient2_user_id}",
        headers=headers,
        json={"role": "staff"},
    )
    assert_error(missing_profile, 422, "validation_failed")

    promoted = client.patch(
        f"/api/v1/users/{seed.patient2_user_id}",
        headers=headers,
        json={"role": "staff", "full_name": "Nurse Two", "staff_type": "nurse"},
    )
    assert promoted.status_code == 200, promoted.get_json()
    assert promoted.get_json()["staff_type"] == "nurse"
    assert isinstance(promoted.get_json()["staff_id"], int)


def test_admin_cannot_lock_itself_out(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.admin_email)
    assert_error(
        client.patch(
            f"/api/v1/users/{seed.admin_user_id}",
            headers=headers,
            json={"is_active": False},
        ),
        400,
        "bad_request",
    )
    assert_error(
        client.patch(
            f"/api/v1/users/{seed.admin_user_id}",
            headers=headers,
            json={"role": "staff"},
        ),
        400,
        "bad_request",
    )


def test_user_management_requires_admin(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.doctor_email)
    assert_error(client.get("/api/v1/users", headers=headers), 403, "forbidden")
    assert_error(
        client.post("/api/v1/users", headers=headers, json={}), 403, "forbidden"
    )
    assert_error(
        client.patch(
            f"/api/v1/users/{seed.patient1_user_id}",
            headers=headers,
            json={"is_active": False},
        ),
        403,
        "forbidden",
    )


def test_patient_list_filters_and_profile_update(
    client: FlaskClient, seed: SeedData
) -> None:
    headers = auth_headers(client, seed.doctor_email)

    listed = client.get("/api/v1/patients", headers=headers)
    assert listed.status_code == 200, listed.get_json()
    assert len(listed.get_json()) == 2

    searched = client.get("/api/v1/patients?q=Two&gender=female", headers=headers)
    assert len(searched.get_json()) == 1
    assert searched.get_json()[0]["patient_id"] == seed.patient2_id
    wildcard = client.get("/api/v1/patients?q=%", headers=headers)
    assert wildcard.get_json() == []

    patient_headers = auth_headers(client, seed.patient1_email)
    updated = client.put(
        f"/api/v1/patients/{seed.patient1_id}",
        headers=patient_headers,
        json={
            "full_name": "Patient Updated",
            "phone": "+15559998888",
            "address": "12 Clinic Road",
        },
    )
    assert updated.status_code == 200, updated.get_json()
    assert updated.get_json()["full_name"] == "Patient Updated"
    assert updated.get_json()["address"] == "12 Clinic Road"

    persisted = client.get(
        f"/api/v1/patients/{seed.patient1_id}", headers=patient_headers
    )
    assert persisted.get_json()["phone"] == "+15559998888"

    invalid = client.put(
        f"/api/v1/patients/{seed.patient1_id}",
        headers=patient_headers,
        json={
            "full_name": "",
            "birth_date": (date.today() + timedelta(days=1)).isoformat(),
            "gender": "alien",
        },
    )
    body = assert_error(invalid, 422, "validation_failed")
    fields = {item["field"] for item in body["error"]["details"]}
    assert {"full_name", "birth_date", "gender"}.issubset(fields)

    assert_error(
        client.get("/api/v1/patients/999999", headers=headers), 404, "not_found"
    )


def test_staff_list_filters_and_availability_validation(
    client: FlaskClient, seed: SeedData
) -> None:
    headers = auth_headers(client, seed.patient1_email)

    listed = client.get("/api/v1/staff", headers=headers)
    assert listed.status_code == 200, listed.get_json()
    assert len(listed.get_json()) == 2

    filtered = client.get("/api/v1/staff?staff_type=physiotherapist", headers=headers)
    assert len(filtered.get_json()) == 1
    assert filtered.get_json()[0]["staff_id"] == seed.physio_id

    searched = client.get("/api/v1/staff?q=Doctor", headers=headers)
    assert len(searched.get_json()) == 1
    wildcard = client.get("/api/v1/staff?q=%", headers=headers)
    assert wildcard.get_json() == []

    assert_error(
        client.get(f"/api/v1/staff/{seed.doctor_id}/availability", headers=headers),
        400,
        "bad_request",
    )
    assert_error(
        client.get(
            f"/api/v1/staff/999999/availability?date={date.today().isoformat()}",
            headers=headers,
        ),
        404,
        "not_found",
    )
