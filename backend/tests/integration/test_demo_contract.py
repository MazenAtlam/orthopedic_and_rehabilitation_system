from datetime import time, timedelta
from decimal import Decimal

import bcrypt
import pytest
from sqlalchemy import select

from app.models.schema_v1 import appointment, medical_record, patient, staff, user
from app.utils.common import utcnow
from scripts.seed import ADMIN, OTHER, PATIENT, PHYSIO, STAFF, THIRD


def service_map(client, headers):
    result = client.get("/api/v1/services", headers=headers)
    assert result.status_code == 200
    return {entry["name"]: entry for entry in result.json["items"]}


def test_seed_matches_the_readme_and_is_idempotent(app, client, tokens):
    runner = app.test_cli_runner()
    reply = runner.invoke(args=["seed-demo"])
    assert reply.exit_code == 0 and "already loaded" in reply.output
    engine = app.extensions["ortho_db"]
    with engine.connect() as connection:
        accounts = {
            row["email"]: row for row in connection.execute(select(user)).mappings()
        }
        assert {email: row["role"] for email, row in accounts.items()} == {
            ADMIN: "admin",
            STAFF: "staff",
            PHYSIO: "staff",
            PATIENT: "patient",
            OTHER: "patient",
            THIRD: "patient",
        }
        hashes = [row["password_hash"].encode() for row in accounts.values()]
        assert len(set(hashes)) == 6
        assert all(
            value.startswith(b"$2b$") and bcrypt.checkpw(b"Test@12345", value)
            for value in hashes
        )
        assert dict(
            connection.execute(select(staff.c.user_id, staff.c.staff_type))
            .tuples()
            .all()
        ) == {
            accounts[STAFF]["user_id"]: "doctor",
            accounts[PHYSIO]["user_id"]: "physiotherapist",
        }
        owned = (
            select(patient.c.patient_id)
            .where(patient.c.user_id == accounts[PATIENT]["user_id"])
            .scalar_subquery()
        )
        doctor = (
            select(staff.c.staff_id)
            .where(staff.c.user_id == accounts[STAFF]["user_id"])
            .scalar_subquery()
        )
        slot = connection.execute(
            select(appointment.c.start_time, appointment.c.end_time).where(
                appointment.c.patient_id == owned,
                appointment.c.staff_id == doctor,
                appointment.c.status == "booked",
            )
        ).one()
        assert slot.start_time.date() == utcnow().date() + timedelta(days=1)
        assert slot.start_time.time() == time(10)
        assert slot.end_time - slot.start_time == timedelta(minutes=30)
        assert len(connection.scalars(select(medical_record.c.record_id)).all()) == 2

    assert {
        name: item["price"]
        for name, item in service_map(client, tokens["patient"]).items()
    } == {
        "Consultation": "300.00",
        "Physio session": "250.00",
        "X-ray imaging": "400.00",
    }
    only_bill = client.get("/api/v1/invoices", headers=tokens["patient"]).json
    assert only_bill["total"] == 1
    row = only_bill["items"][0]
    assert (row["total_amount"], row["balance"], row["status"]) == (
        "500.00",
        "500.00",
        "unpaid",
    )


@pytest.mark.parametrize(
    ("setting", "value"), [("DEMO_MODE", False), ("APP_ENV", "production")]
)
def test_seed_refuses_to_run_outside_development_demo(app, monkeypatch, setting, value):
    monkeypatch.setitem(app.config, setting, value)
    reply = app.test_cli_runner().invoke(args=["seed-demo"])
    assert reply.exit_code == 1
    assert "non-production DEMO_MODE=1" in reply.output


def test_contract_invoice_lines_and_price_snapshot(client, tokens, people):
    headers = tokens["admin"]
    prices = service_map(client, headers)
    consultation = prices["Consultation"]
    physio = prices["Physio session"]
    rejected = client.post(
        "/api/v1/invoices",
        headers=headers,
        json={
            "patient_id": people[0],
            "due_date": utcnow().date().isoformat(),
            "items": [{"service_id": consultation["service_id"], "quantity": 0}],
        },
    )
    assert rejected.status_code == 422
    assert (
        client.post(
            "/api/v1/services",
            headers=headers,
            json={"name": "Negative", "price": "-1.00"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/services",
            headers=tokens["patient"],
            json={"name": "Forbidden", "price": "1.00"},
        ).status_code
        == 403
    )
    invoice = client.post(
        "/api/v1/invoices",
        headers=headers,
        json={
            "patient_id": people[0],
            "due_date": utcnow().date().isoformat(),
            "items": [
                {"service_id": consultation["service_id"], "quantity": 1},
                {"service_id": physio["service_id"], "quantity": 2},
            ],
        },
    )
    assert invoice.status_code == 201
    assert invoice.json["total_amount"] == "800.00"
    assert {
        line["service_id"]: (line["quantity"], line["unit_price"])
        for line in invoice.json["items"]
    } == {
        consultation["service_id"]: (1, "300.00"),
        physio["service_id"]: (2, "250.00"),
    }
    updated = client.post(
        "/api/v1/services",
        headers=headers,
        json={**consultation, "price": "350.00"},
    )
    assert updated.status_code == 200
    try:
        saved = client.get(
            f"/api/v1/invoices/{invoice.json['invoice_id']}", headers=headers
        ).json
        assert saved["total_amount"] == "800.00"
        assert any(
            line["service_id"] == consultation["service_id"]
            and line["unit_price"] == "300.00"
            for line in saved["items"]
        )
    finally:
        restored = client.post("/api/v1/services", headers=headers, json=consultation)
        assert restored.status_code == 200


def test_patient_can_pay_online_but_cannot_pay_by_card(client, tokens, people):
    physio = service_map(client, tokens["admin"])["Physio session"]
    bill = client.post(
        "/api/v1/invoices",
        headers=tokens["staff"],
        json={
            "patient_id": people[0],
            "due_date": utcnow().date().isoformat(),
            "items": [{"service_id": physio["service_id"], "quantity": 2}],
        },
    )
    assert bill.status_code == 201
    url = f"/api/v1/invoices/{bill.json['invoice_id']}/payments"

    def pay(method, amount, key):
        return client.post(
            url,
            headers={**tokens["patient"], "Idempotency-Key": key},
            json={"amount": amount, "method": method},
        )

    for method in ("card", "cash"):
        assert pay(method, "500.00", method).status_code == 403
    for amount in ("0.00", "-10.00"):
        assert pay("online", amount, "invalid-" + amount).status_code == 422
    paid = pay("online", "500.00", "full-demo-payment")
    assert paid.status_code == 201
    assert paid.json["payment"]["status"] == "success"
    assert Decimal(paid.json["invoice"]["balance"]) == 0
    assert paid.json["invoice"]["status"] == "paid"


@pytest.mark.parametrize(
    ("section", "allowed"),
    [
        ("system", {"admin"}),
        ("patients", {"admin", "staff"}),
        ("financial", {"admin"}),
    ],
)
def test_report_permissions_and_payloads(client, tokens, section, allowed):
    for role in ("admin", "staff", "patient"):
        report = client.get(f"/api/v1/reports/{section}", headers=tokens[role])
        if role in allowed:
            assert report.status_code == 200
            assert report.json["daily"] and report.json["totals"]
        else:
            assert report.status_code == 403
