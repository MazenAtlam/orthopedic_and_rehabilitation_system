"""Comprehensive full-system database, REST API, and HL7 FHIR R4 E2E tests."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import AuditLog, Patient, Service, metadata


def _future_slot(days_ahead: int, hour: int, minute: int = 0) -> tuple[str, str]:
    day = datetime.now(timezone.utc).date() + timedelta(days=days_ahead)
    start = datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)
    end = start + timedelta(minutes=30)
    return (
        start.isoformat().replace("+00:00", "Z"),
        end.isoformat().replace("+00:00", "Z"),
    )


def test_database_constraints_restrict_deletes_and_overlap_exclusion(
    app, people
) -> None:
    """Verify PostgreSQL DDL: 17 tables, RESTRICT FKs, CheckConstraints, GiST."""
    engine = app.extensions["ortho_db"]
    inspector = inspect(engine)

    table_names = set(inspector.get_table_names())
    expected_tables = {
        "user",
        "patient",
        "staff",
        "appointment",
        "icd10_code",
        "medical_record",
        "prescription",
        "treatment_plan",
        "rehab_session",
        "scan",
        "cdss_result",
        "annotation",
        "service",
        "invoice",
        "invoice_item",
        "payment",
        "audit_log",
    }
    assert expected_tables.issubset(table_names)
    assert set(metadata.tables) == expected_tables

    # Every foreign key across all 17 tables must enforce ON DELETE RESTRICT
    for table in expected_tables:
        for fk in inspector.get_foreign_keys(table):
            assert (
                fk.get("options", {}).get("ondelete") == "RESTRICT"
            ), f"Table {table} FK {fk['name']} missing ON DELETE RESTRICT"

    patient_id, _, staff_id = people

    with engine.begin() as conn:
        # 1. ON DELETE RESTRICT prevents deleting a referenced patient
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(
                Patient.__table__.delete().where(Patient.patient_id == patient_id)
            )

        # 2. CheckConstraint rejects invalid user role ('guest') at DB level
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(
                text(
                    'INSERT INTO "user" (email, password_hash, role, is_active) '
                    "VALUES ('badrole@hcis.test', 'hash', 'guest', true)"
                )
            )

        # 3. CheckConstraint rejects negative service price at DB level
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(
                Service.__table__.insert().values(
                    name="Invalid Negative Service",
                    price=Decimal("-5.00"),
                    is_active=True,
                )
            )

        # 4. PostgreSQL btree_gist ExcludeConstraint blocks overlapping booked slots
        start_a = datetime(2027, 5, 10, 9, 0, tzinfo=timezone.utc)
        end_a = datetime(2027, 5, 10, 9, 30, tzinfo=timezone.utc)
        start_b = datetime(2027, 5, 10, 9, 15, tzinfo=timezone.utc)
        end_b = datetime(2027, 5, 10, 9, 45, tzinfo=timezone.utc)
        insert_sql = text(
            "INSERT INTO appointment "
            "(patient_id, staff_id, type, start_time, end_time, status) "
            "VALUES (:pid, :sid, 'consultation', :s, :e, 'booked')"
        )
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(
                insert_sql,
                {"pid": patient_id, "sid": staff_id, "s": start_a, "e": end_a},
            )
            conn.execute(
                insert_sql,
                {"pid": patient_id, "sid": staff_id, "s": start_b, "e": end_b},
            )

    # 5. Append-only audit_log trigger blocks UPDATE, DELETE, and TRUNCATE
    for stmt in (
        "UPDATE audit_log SET action = 'mutated'",
        "DELETE FROM audit_log",
        "TRUNCATE audit_log",
    ):
        with pytest.raises(DBAPIError) as exc, engine.begin() as conn:
            conn.execute(text(stmt))
        assert exc.value.orig.sqlstate == "55000"


def test_end_to_end_patient_clinical_rehab_billing_and_fhir_journey(
    app, client
) -> None:
    """Test a complete hospital lifecycle across REST (/api/v1) and HL7 FHIR R4."""
    # 1. Admin logs in via /api/v1/auth/login and creates a doctor account
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@hcis.test", "password": "Test@12345"},
    )
    assert admin_login.status_code == 200, admin_login.get_json()
    admin_headers = {
        "Authorization": f"Bearer {admin_login.get_json()['access_token']}"
    }

    doc_res = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "e2e.doctor@hcis.test",
            "password": "Test@12345",
            "role": "staff",
            "full_name": "Dr. E2E Ortho",
            "staff_type": "doctor",
            "specialty": "Orthopedic Surgery",
        },
    )
    assert doc_res.status_code == 201, doc_res.get_json()
    doctor_staff_id = doc_res.get_json()["staff_id"]

    # 2. New patient self-registers, logs in, and refreshes token via HttpOnly cookie
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Salma E2E Patient",
            "email": "salma.e2e@hcis.test",
            "password": "Test@12345",
            "birth_date": "1994-08-15",
            "gender": "female",
            "phone": "+201012345678",
        },
    )
    assert reg_res.status_code == 201, reg_res.get_json()
    patient_id = reg_res.get_json()["patient_id"]

    pat_login = client.post(
        "/api/v1/auth/login",
        json={"email": "salma.e2e@hcis.test", "password": "Test@12345"},
    )
    assert pat_login.status_code == 200
    refresh_res = client.post("/api/v1/auth/refresh")
    assert refresh_res.status_code == 200
    pat_headers = {"Authorization": f"Bearer {refresh_res.get_json()['access_token']}"}

    doc_login = client.post(
        "/api/v1/auth/login",
        json={"email": "e2e.doctor@hcis.test", "password": "Test@12345"},
    )
    assert doc_login.status_code == 200
    doc_headers = {"Authorization": f"Bearer {doc_login.get_json()['access_token']}"}

    # 3. Patient checks doctor availability & books slot; booked slot disappears
    start_iso, end_iso = _future_slot(12, 11, 0)
    slot_day = start_iso[:10]
    avail_before = client.get(
        f"/api/v1/staff/{doctor_staff_id}/availability?date={slot_day}",
        headers=pat_headers,
    )
    assert avail_before.status_code == 200
    assert start_iso in avail_before.get_json()

    booked = client.post(
        "/api/v1/appointments",
        headers=pat_headers,
        json={
            "patient_id": patient_id,
            "staff_id": doctor_staff_id,
            "type": "consultation",
            "start_time": start_iso,
            "end_time": end_iso,
            "notes": "Right knee locking",
        },
    )
    assert booked.status_code == 201, booked.get_json()
    appointment_id = booked.get_json()["appointment_id"]

    avail_after = client.get(
        f"/api/v1/staff/{doctor_staff_id}/availability?date={slot_day}",
        headers=pat_headers,
    )
    assert start_iso not in avail_after.get_json()

    # Doctor marks appointment completed
    completed = client.patch(
        f"/api/v1/appointments/{appointment_id}",
        headers=doc_headers,
        json={"status": "completed"},
    )
    assert completed.status_code == 200
    assert completed.get_json()["status"] == "completed"

    # 4. Doctor searches ICD-10, creates visit + prescription + rehab plan + session
    icd_lookup = client.get("/api/v1/icd10?q=M17.9", headers=doc_headers)
    assert icd_lookup.status_code == 200
    assert any(item["code"] == "M17.9" for item in icd_lookup.get_json())

    today_str = date.today().isoformat()
    visit_res = client.post(
        "/api/v1/records",
        headers=doc_headers,
        json={
            "patient_id": patient_id,
            "appointment_id": appointment_id,
            "visit_date": today_str,
            "chief_complaint": "Medial knee pain",
            "affected_area": "Right Knee",
            "diagnosis": "Knee osteoarthritis",
            "icd10_code": "M17.9",
            "notes": "CONFIDENTIAL E2E CLINICAL NOTE",
        },
    )
    assert visit_res.status_code == 201, visit_res.get_json()
    record_id = visit_res.get_json()["record_id"]

    rx_res = client.post(
        f"/api/v1/records/{record_id}/prescriptions",
        headers=doc_headers,
        json={
            "medication": "Naproxen",
            "dose": "500 mg",
            "frequency": "Twice daily",
            "duration": "10 days",
            "instructions": "After meals",
        },
    )
    assert rx_res.status_code == 201, rx_res.get_json()

    plan_res = client.post(
        "/api/v1/treatment-plans",
        headers=doc_headers,
        json={
            "patient_id": patient_id,
            "record_id": record_id,
            "title": "E2E Knee Strengthening Protocol",
            "goal": "Achieve 130 deg flexion",
            "start_date": today_str,
            "end_date": (date.today() + timedelta(days=28)).isoformat(),
        },
    )
    assert plan_res.status_code == 201, plan_res.get_json()
    plan_id = plan_res.get_json()["plan_id"]

    sess_res = client.post(
        f"/api/v1/treatment-plans/{plan_id}/sessions",
        headers=doc_headers,
        json={
            "session_date": today_str,
            "exercises": "Quad sets and straight-leg raises",
            "pain_score": 4,
            "range_of_motion": 115,
            "notes": "Good quad activation",
        },
    )
    assert sess_res.status_code == 201, sess_res.get_json()

    # 5. Admin creates EGP service; Doctor bills patient; Patient pays in two steps
    svc_res = client.post(
        "/api/v1/services",
        headers=admin_headers,
        json={
            "name": "E2E Ortho Assessment",
            "price": "450.00",
            "is_active": True,
        },
    )
    assert svc_res.status_code == 201
    svc_id = svc_res.get_json()["service_id"]

    inv_res = client.post(
        "/api/v1/invoices",
        headers=doc_headers,
        json={
            "patient_id": patient_id,
            "appointment_id": appointment_id,
            "icd10_code": "M17.9",
            "issue_date": today_str,
            "due_date": (date.today() + timedelta(days=14)).isoformat(),
            "items": [{"service_id": svc_id, "quantity": 2}],
        },
    )
    assert inv_res.status_code == 201, inv_res.get_json()
    inv_id = inv_res.get_json()["invoice_id"]
    assert inv_res.get_json()["total_amount"] == "900.00"

    partial_pay = client.post(
        f"/api/v1/invoices/{inv_id}/payments",
        headers={**pat_headers, "Idempotency-Key": "e2e-pay-1"},
        json={"amount": "400.00", "method": "online"},
    )
    assert partial_pay.status_code == 201
    assert partial_pay.get_json()["invoice"]["status"] == "partial"
    assert partial_pay.get_json()["invoice"]["balance"] == "500.00"

    final_pay = client.post(
        f"/api/v1/invoices/{inv_id}/payments",
        headers={**pat_headers, "Idempotency-Key": "e2e-pay-2"},
        json={"amount": "500.00", "method": "online"},
    )
    assert final_pay.status_code == 201
    assert final_pay.get_json()["invoice"]["status"] == "paid"
    assert final_pay.get_json()["invoice"]["balance"] == "0.00"

    # 6. Reports reflect the new visit and 900.00 EGP payment
    fin_report = client.get(
        f"/api/v1/reports/financial?start={today_str}&end={today_str}",
        headers=admin_headers,
    )
    assert fin_report.status_code == 200
    assert Decimal(fin_report.get_json()["totals"]["revenue"]) >= Decimal("900.00")

    pat_report = client.get(
        f"/api/v1/reports/patients?start={today_str}&end={today_str}",
        headers=doc_headers,
    )
    assert pat_report.status_code == 200
    assert any(d["code"] == "M17.9" for d in pat_report.get_json()["diagnoses"])

    # 7. Bidirectional FHIR R4 interoperability check (EMR Client consumer contract)
    for clinical_type in (
        "Appointment",
        "Encounter",
        "Condition",
        "MedicationRequest",
        "CarePlan",
        "Procedure",
        "Observation",
    ):
        bundle = client.get(
            f"/api/v1/fhir/{clinical_type}?patient=Patient/{patient_id}",
            headers=pat_headers,
        )
        assert bundle.status_code == 200, (clinical_type, bundle.get_json())
        assert bundle.mimetype == "application/fhir+json"
        assert bundle.get_json()["total"] >= 1

    for billing_type in ("Invoice", "PaymentNotice"):
        bundle = client.get(
            f"/api/v1/fhir/{billing_type}",
            headers=pat_headers,
        )
        assert bundle.status_code == 200, (billing_type, bundle.get_json())
        assert bundle.mimetype == "application/fhir+json"
        assert bundle.get_json()["total"] >= 1

    # 8. Verify audit_log never leaked clinical notes or medication names
    engine = app.extensions["ortho_db"]
    with engine.connect() as conn:
        audit_strings = " ".join(
            f"{a} {r}"
            for a, r in conn.execute(
                select(AuditLog.action, AuditLog.resource)
            ).tuples()
        )
    assert "CONFIDENTIAL E2E CLINICAL NOTE" not in audit_strings
    assert "Naproxen" not in audit_strings
