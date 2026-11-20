from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError

from ortho.common import utcnow
from ortho.fhir_resources import ICD10_SYSTEM
from ortho.schema_v1 import audit_log, metadata


def bill_for(client, headers, patient_id, *, service_id=1, due=None):
    response = client.post("/api/v1/invoices", headers=headers, json={
        "patient_id": patient_id, "due_date": due or (utcnow().date() + timedelta(days=14)).isoformat(),
        "items": [{"service_id": service_id, "quantity": 1}],
        "icd10_code": "M25.5",
    })
    assert response.status_code == 201, response.json
    return response.json


def payment_for(client, headers, bill_id, amount, key, result="success"):
    return client.post(f"/api/v1/invoices/{bill_id}/payments",
                       headers={**headers, "Idempotency-Key": key},
                       json={"amount": amount, "method": "online", "simulate": result})


def test_schema_and_append_only_audit(app, client, tokens):
    assert client.get("/api/v1/fhir/Encounter", headers=tokens["staff"]).status_code == 200
    engine = app.extensions["ortho_db"]
    assert set(inspect(engine).get_table_names()) == {*metadata.tables, "alembic_version"}
    with engine.connect() as connection:
        seed_count = connection.scalar(text("SELECT COUNT(*) FROM patient"))
        assert seed_count == 2
        assert connection.scalar(select(audit_log.c.action).where(audit_log.c.action == "read").limit(1))
    for statement in ("UPDATE audit_log SET action='tampered'", "DELETE FROM audit_log", "TRUNCATE audit_log"):
        with pytest.raises(DBAPIError) as error, engine.begin() as connection:
            connection.execute(text(statement))
        assert error.value.orig.sqlstate == "55000"


def test_catalogue_prices_are_snapshots(client, tokens, people):
    new = client.post("/api/v1/services", headers=tokens["admin"], json={"name": "Snapshot test", "price": "90.25"})
    assert new.status_code == 201
    item_id = new.json["service_id"]
    bill = bill_for(client, tokens["staff"], people[0], service_id=item_id)
    reprice = client.post("/api/v1/services", headers=tokens["admin"], json={
        "service_id": item_id, "name": "Snapshot test", "price": "110.00", "is_active": False,
    })
    assert reprice.status_code == 200
    read = client.get(f"/api/v1/invoices/{bill['invoice_id']}", headers=tokens["patient"]).json
    assert read["total_amount"] == read["items"][0]["unit_price"] == "90.25"
    active = client.get("/api/v1/services", headers=tokens["patient"]).json
    assert all(item["service_id"] != item_id for item in active["items"])
    attempt = client.post("/api/v1/services", headers=tokens["staff"], json={})
    assert attempt.status_code == 403


def test_payment_decline_partial_replay_and_full(client, tokens, people):
    item = bill_for(client, tokens["staff"], people[0])
    invoice_id = item["invoice_id"]
    rejected = payment_for(client, tokens["patient"], invoice_id, "125.00", "reject", "declined")
    assert (rejected.status_code, rejected.json["payment"]["status"]) == (201, "failed")
    assert rejected.json["invoice"]["balance"] == item["total_amount"]

    first = payment_for(client, tokens["patient"], invoice_id, "125.00", "approved")
    assert (first.status_code, first.json["invoice"]["status"], first.json["invoice"]["balance"]) == (
        201, "partial", "325.00",
    )
    repeat = payment_for(client, tokens["patient"], invoice_id, "125.00", "approved")
    assert repeat.status_code == 200 and repeat.json["payment"] == first.json["payment"]
    collision = payment_for(client, tokens["patient"], invoice_id, "126.00", "approved")
    assert collision.status_code == 409
    invalid = payment_for(client, tokens["patient"], invoice_id, "0.001", "three-decimals")
    assert invalid.status_code == 422
    overpayment = payment_for(client, tokens["patient"], invoice_id, "325.01", "over")
    assert overpayment.status_code == 409
    last = payment_for(client, tokens["patient"], invoice_id, "325.00", "final")
    assert (last.status_code, last.json["invoice"]["status"], last.json["invoice"]["balance"]) == (
        201, "paid", "0.00",
    )
    assert len(last.json["invoice"]["payments"]) == 3
    assert payment_for(client, tokens["patient"], invoice_id, "1.00", "paid").status_code == 409


def test_two_simultaneous_payments_cannot_overpay(app, client, tokens, people):
    bill = bill_for(client, tokens["staff"], people[0])
    invoice_id = bill["invoice_id"]
    barrier = Barrier(2, timeout=10)

    def submit(index):
        with app.test_client() as worker:
            barrier.wait()
            return payment_for(worker, tokens["patient"], invoice_id, "300.00", f"race-{index}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sorted(result.status_code for result in results) == [201, 409]
    read = client.get(f"/api/v1/invoices/{invoice_id}", headers=tokens["patient"]).json
    assert read["balance"] == "150.00" and len(read["payments"]) == 1


def test_invoice_ownership_and_role_matrix(client, tokens, people):
    bill = bill_for(client, tokens["staff"], people[0])
    url = f"/api/v1/invoices/{bill['invoice_id']}"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=tokens["other"]).status_code == 404
    assert client.get(url, headers=tokens["staff"]).status_code == 200
    assert client.get(url, headers=tokens["admin"]).status_code == 200
    assert payment_for(client, tokens["other"], bill["invoice_id"], "10.00", "wrong-user").status_code == 404
    assert payment_for(client, tokens["staff"], bill["invoice_id"], "10.00", "wrong-staff").status_code == 403
    listing = client.get(f"/api/v1/invoices?patient_id={people[0]}", headers=tokens["other"])
    assert listing.json["total"] == 0


def test_reports_match_seeded_historical_payments_and_visits(client, tokens):
    start = (utcnow().date() - timedelta(days=10)).isoformat()
    end = (utcnow().date() - timedelta(days=4)).isoformat()
    filters = f"?start={start}&end={end}"
    financial = client.get(f"/api/v1/reports/financial{filters}", headers=tokens["admin"])
    assert financial.status_code == 200
    assert Decimal(financial.json["totals"]["revenue"]) == Decimal("150.00")
    assert Decimal(financial.json["totals"]["outstanding"]) == Decimal("750.00")
    assert financial.json["totals"]["open_invoices"] == 2
    stats = client.get(f"/api/v1/reports/patients{filters}", headers=tokens["staff"]).json
    assert stats["totals"] == {"patients": 2, "visits": 2}
    assert {row["code"] for row in stats["diagnoses"]} == {"M25.5", "M54.5"}
    system = client.get(f"/api/v1/reports/system{filters}", headers=tokens["admin"]).json
    assert system["appointments_by_status"]["completed"] == 2
    assert client.get("/api/v1/reports/system", headers=tokens["staff"]).status_code == 403
    assert client.get("/api/v1/reports/financial", headers=tokens["staff"]).status_code == 403
    assert client.get("/api/v1/reports/patients", headers=tokens["patient"]).status_code == 403
    invalid = client.get(f"/api/v1/reports/system?start={end}&end={start}", headers=tokens["admin"])
    assert invalid.status_code == 422


def test_icd10_search_and_invalid_invoice_code(client, tokens, people):
    result = client.get("/api/v1/icd10?q=m25", headers=tokens["staff"])
    assert result.status_code == 200 and result.json["items"][0]["code"] == "M25.5"
    assert client.get("/api/v1/icd10", headers=tokens["patient"]).status_code == 403
    result = client.post("/api/v1/invoices", headers=tokens["staff"], json={
        "patient_id": people[0], "due_date": utcnow().date().isoformat(),
        "icd10_code": "ZZZ", "items": [{"service_id": 1, "quantity": 1}],
    })
    assert result.status_code == 422 and result.json["error"]["code"] == "code-invalid"


@pytest.mark.parametrize("kind", [
    "Patient", "Practitioner", "Appointment", "Encounter", "Condition", "MedicationRequest",
    "CarePlan", "Procedure", "Observation", "Invoice", "PaymentNotice",
])
def test_each_fhir_mapping_can_be_searched_and_read(client, tokens, kind):
    path = f"/api/v1/fhir/{kind}"
    bundle = client.get(f"{path}?_count=1", headers=tokens["staff"])
    assert bundle.status_code == 200, bundle.json
    assert bundle.mimetype == "application/fhir+json"
    assert bundle.json["type"] == "searchset"
    entry = bundle.json["entry"][0]
    resource = entry["resource"]
    assert resource["resourceType"] == kind and entry["fullUrl"].endswith(f"/{kind}/{resource['id']}")
    single = client.get(f"{path}/{resource['id']}", headers=tokens["staff"])
    assert single.status_code == 200 and single.json == resource
    if bundle.json["total"] > 1:
        next_page = next(link["url"] for link in bundle.json["link"] if link["relation"] == "next")
        assert client.get(next_page, headers=tokens["staff"]).json["entry"][0]["resource"]["id"] != resource["id"]


def test_fhir_scope_and_diagnosis_coding(client, tokens, people):
    path = "/api/v1/fhir"
    own, other, _ = people
    denied = client.get(f"{path}/Patient/{other}", headers=tokens["patient"])
    assert denied.status_code == 404 and denied.json["resourceType"] == "OperationOutcome"
    denied_list = client.get(f"{path}/Encounter?patient=Patient/{other}", headers=tokens["patient"])
    assert denied_list.json["total"] == 0
    records = client.get(f"{path}/Condition?patient=Patient/{own}", headers=tokens["patient"]).json["entry"]
    condition = records[0]["resource"]
    assert condition["code"]["coding"][0]["system"] == ICD10_SYSTEM
    assert condition["code"]["coding"][0]["code"] == "M25.5"
    assert client.get(f"{path}/Condition", headers=tokens["admin"]).status_code == 403
    assert client.get(f"{path}/Practitioner", headers=tokens["patient"]).status_code == 403
    assert client.get(f"{path}/Patient").json["resourceType"] == "OperationOutcome"
    metadata = client.get(f"{path}/metadata", headers=tokens["staff"]).json
    assert metadata["fhirVersion"] == "4.0.1"
    route = next(resource for resource in metadata["rest"][0]["resource"] if resource["type"] == "Appointment")
    assert {"code": "create"} in route["interaction"]


def test_fhir_appointment_creation_overlap_and_adjacency(client, tokens, people):
    start = (utcnow() + timedelta(days=5)).replace(microsecond=0)
    end = start + timedelta(minutes=30)
    data = {
        "resourceType": "Appointment", "status": "booked",
        "start": start.isoformat(), "end": end.isoformat(),
        "participant": [
            {"actor": {"reference": f"Patient/{people[0]}"}, "status": "accepted"},
            {"actor": {"reference": f"Practitioner/{people[2]}"}, "status": "accepted"},
        ],
        "appointmentType": {"text": "therapy"},
    }
    path = "/api/v1/fhir/Appointment"

    def schedule(role, appointment):
        return client.post(path, headers=tokens[role], json=appointment, content_type="application/fhir+json")

    unauthorized = schedule("patient", data)
    assert unauthorized.status_code == 403
    response = schedule("staff", data)
    assert response.status_code == 201
    assert response.headers["Location"].endswith(f"/Appointment/{response.json['id']}")
    assert schedule("staff", data).status_code == 409
    adjacent = {**data, "start": end.isoformat(), "end": (end + timedelta(minutes=30)).isoformat()}
    assert schedule("staff", adjacent).status_code == 201
