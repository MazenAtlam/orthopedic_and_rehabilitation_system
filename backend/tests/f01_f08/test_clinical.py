"""F06-F08 EMR, prescription and rehabilitation integration tests."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from flask.testing import FlaskClient
from sqlalchemy import func, select

from app.extensions import db
from app.models import AuditLog, MedicalRecord, Prescription, RehabSession
from tests.f01_f08.conftest import SeedData, assert_error, auth_headers


def record_payload(seed: SeedData, **overrides: Any) -> dict[str, Any]:
    """Build a valid visit-record payload."""
    payload: dict[str, Any] = {
        "patient_id": seed.patient1_id,
        "visit_date": date.today().isoformat(),
        "chief_complaint": "Left knee pain",
        "affected_area": "left knee",
        "diagnosis": "Knee osteoarthritis",
        "icd10_code": "m17.9",
        "notes": "SECRET CLINICAL NOTE",
    }
    payload.update(overrides)
    return payload


def plan_payload(seed: SeedData, **overrides: Any) -> dict[str, Any]:
    """Build a valid rehabilitation-plan payload."""
    payload: dict[str, Any] = {
        "patient_id": seed.patient1_id,
        "title": "Knee rehabilitation",
        "goal": "Restore pain-free range of motion",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=30)).isoformat(),
    }
    payload.update(overrides)
    return payload


def session_payload(**overrides: Any) -> dict[str, Any]:
    """Build a valid rehab-session payload."""
    payload: dict[str, Any] = {
        "pain_score": 7,
        "range_of_motion": 95,
        "exercises": "Heel slides and knee extensions",
        "notes": "Tolerated well",
    }
    payload.update(overrides)
    return payload


def test_icd10_lookup_searches_reference_data(
    client: FlaskClient, seed: SeedData
) -> None:
    headers = auth_headers(client, seed.doctor_email)
    response = client.get("/api/v1/icd10?q=knee", headers=headers)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["code"] == "M17.9"
    assert "knee" in body[0]["description"].lower()

    empty = client.get("/api/v1/icd10?q=zzzz", headers=headers)
    assert empty.get_json() == []


def test_icd10_lookup_lists_all_codes_and_treats_wildcards_literally(
    client: FlaskClient, seed: SeedData
) -> None:
    headers = auth_headers(client, seed.doctor_email)

    all_codes = client.get("/api/v1/icd10", headers=headers)
    assert all_codes.status_code == 200, all_codes.get_json()
    assert len(all_codes.get_json()) == 2

    for term in ("%", "_"):
        literal = client.get(f"/api/v1/icd10?q={term}", headers=headers)
        assert literal.status_code == 200, literal.get_json()
        assert literal.get_json() == []


def test_create_record_links_patient_staff_and_icd10(
    client: FlaskClient, seed: SeedData
) -> None:
    headers = auth_headers(client, seed.doctor_email)
    response = client.post(
        "/api/v1/records", headers=headers, json=record_payload(seed)
    )
    assert response.status_code == 201, response.get_json()
    record = response.get_json()
    assert record["patient_id"] == seed.patient1_id
    assert record["staff_id"] == seed.doctor_id
    assert record["icd10_code"] == "M17.9"
    assert "knee" in record["icd10_description"].lower()


def test_unknown_icd10_code_is_rejected(client: FlaskClient, seed: SeedData) -> None:
    headers = auth_headers(client, seed.doctor_email)
    body = assert_error(
        client.post(
            "/api/v1/records",
            headers=headers,
            json=record_payload(seed, icd10_code="ZZZ"),
        ),
        422,
        "validation_failed",
    )
    assert any(item["field"] == "icd10_code" for item in body["error"]["details"])
    assert db.session.scalar(select(func.count()).select_from(MedicalRecord)) == 0


def test_record_update_persists_and_history_is_owner_scoped(
    client: FlaskClient, seed: SeedData
) -> None:
    doctor_headers = auth_headers(client, seed.doctor_email)
    patient_headers = auth_headers(client, seed.patient1_email)

    created = client.post(
        "/api/v1/records", headers=doctor_headers, json=record_payload(seed)
    )
    record_id = created.get_json()["record_id"]
    updated = client.put(
        f"/api/v1/records/{record_id}",
        headers=doctor_headers,
        json={"diagnosis": "Updated diagnosis", "notes": None},
    )
    assert updated.status_code == 200, updated.get_json()
    assert updated.get_json()["diagnosis"] == "Updated diagnosis"

    detail = client.get(f"/api/v1/records/{record_id}", headers=patient_headers)
    assert detail.status_code == 200, detail.get_json()
    assert detail.get_json()["diagnosis"] == "Updated diagnosis"

    history = client.get(
        f"/api/v1/patients/{seed.patient1_id}/records", headers=patient_headers
    )
    assert history.status_code == 200, history.get_json()
    assert len(history.get_json()) == 1
    assert all(item["patient_id"] == seed.patient1_id for item in history.get_json())
    assert history.get_json()[0]["staff_name"] == "Doctor One"

    bad_update = assert_error(
        client.put(
            f"/api/v1/records/{record_id}",
            headers=doctor_headers,
            json={"icd10_code": "NOPE"},
        ),
        422,
        "validation_failed",
    )
    assert bad_update["error"]["details"][0]["field"] == "icd10_code"


def test_prescription_creation_and_patient_listing(
    client: FlaskClient, seed: SeedData
) -> None:
    doctor_headers = auth_headers(client, seed.doctor_email)
    record = client.post(
        "/api/v1/records", headers=doctor_headers, json=record_payload(seed)
    )
    record_id = record.get_json()["record_id"]

    payload = {
        "medication": "Ibuprofen",
        "dose": "400 mg",
        "frequency": "three times daily",
        "duration": "7 days",
        "instructions": "Take with food",
    }
    created = client.post(
        f"/api/v1/records/{record_id}/prescriptions",
        headers=doctor_headers,
        json=payload,
    )
    assert created.status_code == 201, created.get_json()
    body = created.get_json()
    assert body["record_id"] == record_id
    assert body["patient_id"] == seed.patient1_id
    assert body["medication"] == "Ibuprofen"

    listed = client.get(
        f"/api/v1/patients/{seed.patient1_id}/prescriptions",
        headers=auth_headers(client, seed.patient1_email),
    )
    assert listed.status_code == 200, listed.get_json()
    assert len(listed.get_json()) == 1
    assert listed.get_json()[0]["dose"] == "400 mg"


def test_prescription_requires_medication(client: FlaskClient, seed: SeedData) -> None:
    doctor_headers = auth_headers(client, seed.doctor_email)
    record = client.post(
        "/api/v1/records", headers=doctor_headers, json=record_payload(seed)
    )
    record_id = record.get_json()["record_id"]
    body = assert_error(
        client.post(
            f"/api/v1/records/{record_id}/prescriptions",
            headers=doctor_headers,
            json={"dose": "400 mg"},
        ),
        422,
        "validation_failed",
    )
    assert body["error"]["details"][0]["field"] == "medication"
    assert db.session.scalar(select(func.count()).select_from(Prescription)) == 0


def test_treatment_plan_creation_filters_and_status_update(
    client: FlaskClient, seed: SeedData
) -> None:
    physio_headers = auth_headers(client, seed.physio_email)
    patient_headers = auth_headers(client, seed.patient1_email)

    created = client.post(
        "/api/v1/treatment-plans",
        headers=physio_headers,
        json=plan_payload(seed),
    )
    assert created.status_code == 201, created.get_json()
    plan = created.get_json()
    assert plan["status"] == "active"
    assert plan["staff_id"] == seed.physio_id
    assert plan["patient_id"] == seed.patient1_id

    invalid_dates = assert_error(
        client.post(
            "/api/v1/treatment-plans",
            headers=physio_headers,
            json=plan_payload(
                seed, end_date=(date.today() - timedelta(days=1)).isoformat()
            ),
        ),
        422,
        "validation_failed",
    )
    assert invalid_dates["error"]["details"][0]["field"] == "end_date"

    filtered = client.get(
        "/api/v1/treatment-plans?status=active&page=1&page_size=1",
        headers=physio_headers,
    )
    assert filtered.status_code == 200, filtered.get_json()
    assert filtered.get_json()["total"] == 1
    assert filtered.get_json()["page_size"] == 1

    own = client.get("/api/v1/treatment-plans", headers=patient_headers)
    assert len(own.get_json()) == 1
    assert own.get_json()[0]["plan_id"] == plan["plan_id"]

    updated = client.patch(
        f"/api/v1/treatment-plans/{plan['plan_id']}",
        headers=physio_headers,
        json={"status": "completed", "goal": "Independent mobility"},
    )
    assert updated.status_code == 200, updated.get_json()
    assert updated.get_json()["status"] == "completed"
    assert updated.get_json()["goal"] == "Independent mobility"

    bad_status = assert_error(
        client.patch(
            f"/api/v1/treatment-plans/{plan['plan_id']}",
            headers=physio_headers,
            json={"status": "paused"},
        ),
        422,
        "validation_failed",
    )
    assert bad_status["error"]["details"][0]["field"] == "status"


def test_rehab_session_pain_score_bounds(client: FlaskClient, seed: SeedData) -> None:
    physio_headers = auth_headers(client, seed.physio_email)
    patient_headers = auth_headers(client, seed.patient1_email)
    plan = client.post(
        "/api/v1/treatment-plans", headers=physio_headers, json=plan_payload(seed)
    )
    plan_id = plan.get_json()["plan_id"]

    created = client.post(
        f"/api/v1/treatment-plans/{plan_id}/sessions",
        headers=physio_headers,
        json=session_payload(),
    )
    assert created.status_code == 201, created.get_json()
    assert created.get_json()["pain_score"] == 7
    assert created.get_json()["range_of_motion"] == 95
    assert created.get_json()["session_date"] == date.today().isoformat()

    for invalid_score in (11, -1):
        body = assert_error(
            client.post(
                f"/api/v1/treatment-plans/{plan_id}/sessions",
                headers=physio_headers,
                json=session_payload(pain_score=invalid_score),
            ),
            422,
            "validation_failed",
        )
        assert any(item["field"] == "pain_score" for item in body["error"]["details"])

    for valid_score in (0, 10):
        response = client.post(
            f"/api/v1/treatment-plans/{plan_id}/sessions",
            headers=physio_headers,
            json=session_payload(pain_score=valid_score),
        )
        assert response.status_code == 201, response.get_json()

    oversized = assert_error(
        client.post(
            f"/api/v1/treatment-plans/{plan_id}/sessions",
            headers=physio_headers,
            json=session_payload(range_of_motion=10000),
        ),
        422,
        "validation_failed",
    )
    assert any(
        item["field"] == "range_of_motion" for item in oversized["error"]["details"]
    )

    sessions = client.get(
        f"/api/v1/treatment-plans/{plan_id}/sessions", headers=patient_headers
    )
    assert sessions.status_code == 200, sessions.get_json()
    assert len(sessions.get_json()) == 3
    assert (
        db.session.scalar(
            select(func.count())
            .select_from(RehabSession)
            .where(RehabSession.plan_id == plan_id)
        )
        == 3
    )


def test_rehab_session_appointment_link_rules(
    client: FlaskClient, seed: SeedData
) -> None:
    physio_headers = auth_headers(client, seed.physio_email)
    plan = client.post(
        "/api/v1/treatment-plans", headers=physio_headers, json=plan_payload(seed)
    )
    plan_id = plan.get_json()["plan_id"]

    linked = client.post(
        f"/api/v1/treatment-plans/{plan_id}/sessions",
        headers=physio_headers,
        json=session_payload(appointment_id=seed.appointment_id),
    )
    assert linked.status_code == 201, linked.get_json()
    assert linked.get_json()["appointment_id"] == seed.appointment_id

    duplicate = assert_error(
        client.post(
            f"/api/v1/treatment-plans/{plan_id}/sessions",
            headers=physio_headers,
            json=session_payload(appointment_id=seed.appointment_id),
        ),
        409,
        "session_exists",
    )
    assert duplicate["error"]["code"] == "session_exists"

    other_plan = client.post(
        "/api/v1/treatment-plans",
        headers=physio_headers,
        json=plan_payload(seed, patient_id=seed.patient2_id, title="Other plan"),
    )
    wrong_patient = assert_error(
        client.post(
            f"/api/v1/treatment-plans/{other_plan.get_json()['plan_id']}/sessions",
            headers=physio_headers,
            json=session_payload(appointment_id=seed.appointment_id),
        ),
        422,
        "validation_failed",
    )
    assert any(
        item["field"] == "appointment_id" for item in wrong_patient["error"]["details"]
    )


def test_clinical_audit_entries_never_store_clinical_content(
    client: FlaskClient, seed: SeedData
) -> None:
    doctor_headers = auth_headers(client, seed.doctor_email)
    physio_headers = auth_headers(client, seed.physio_email)
    assert client.get("/api/v1/icd10?q=knee", headers=doctor_headers).status_code == 200

    record = client.post(
        "/api/v1/records", headers=doctor_headers, json=record_payload(seed)
    )
    record_id = record.get_json()["record_id"]
    client.post(
        f"/api/v1/records/{record_id}/prescriptions",
        headers=doctor_headers,
        json={"medication": "Ibuprofen", "dose": "400 mg"},
    )
    plan = client.post(
        "/api/v1/treatment-plans", headers=physio_headers, json=plan_payload(seed)
    )
    client.post(
        f"/api/v1/treatment-plans/{plan.get_json()['plan_id']}/sessions",
        headers=physio_headers,
        json=session_payload(),
    )

    actions = set(db.session.scalars(select(AuditLog.action)).all())
    resources = set(db.session.scalars(select(AuditLog.resource)).all())
    assert {
        "medical_record_created",
        "prescription_created",
        "treatment_plan_created",
        "rehab_session_created",
    }.issubset(actions)
    assert not any(
        clinical in value
        for value in actions | resources
        for clinical in ("SECRET", "Ibuprofen", "Knee", "diagnosis", "95")
    )
