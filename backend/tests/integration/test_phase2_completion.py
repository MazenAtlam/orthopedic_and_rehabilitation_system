from datetime import date

from sqlalchemy import select

from app.fhir.resources import ICD10_SYSTEM
from app.models import AuditLog, CdssResult, Scan
from app.utils.common import utcnow

audit_log = AuditLog.__table__
cdss_result = CdssResult.__table__
scan = Scan.__table__

FHIR = "/api/v1/fhir"
FHIR_JSON = "application/fhir+json"


def test_staff_can_record_a_diagnosis_and_see_it_in_fhir_and_reports(
    app, client, tokens, people
):
    patient, other, practitioner = people
    visit_date = utcnow().date().isoformat()
    subject = {"reference": f"Patient/{patient}"}
    encounter = {
        "resourceType": "Encounter",
        "status": "finished",
        "class": {"code": "AMB"},
        "subject": subject,
        "period": {"start": visit_date},
        "reasonCode": [{"text": "Fictional follow-up"}],
        "diagnosis": [{"condition": {"reference": "#diagnosis"}}],
        "participant": [{"individual": {"reference": f"Practitioner/{practitioner}"}}],
        "contained": [
            {
                "resourceType": "Condition",
                "id": "diagnosis",
                "subject": subject,
                "code": {
                    "coding": [{"system": ICD10_SYSTEM, "code": "m17.9"}],
                    "text": "Fictional coded diagnosis",
                },
            }
        ],
    }
    for role in ("admin", "patient"):
        assert (
            client.post(
                f"{FHIR}/Encounter",
                headers=tokens[role],
                json=encounter,
                content_type=FHIR_JSON,
            ).status_code
            == 403
        )
    unknown_condition = {
        **encounter["contained"][0],
        "code": {"coding": [{"system": ICD10_SYSTEM, "code": "ZZZ"}]},
    }
    unknown = client.post(
        f"{FHIR}/Encounter",
        headers=tokens["staff"],
        json={**encounter, "contained": [unknown_condition]},
        content_type=FHIR_JSON,
    )
    assert unknown.status_code == 422
    wrong_author = client.post(
        f"{FHIR}/Encounter",
        headers=tokens["staff"],
        json={
            **encounter,
            "participant": [
                {"individual": {"reference": f"Practitioner/{practitioner + 1}"}}
            ],
        },
        content_type=FHIR_JSON,
    )
    assert wrong_author.status_code == 403

    result = client.post(
        f"{FHIR}/Encounter",
        headers=tokens["staff"],
        json=encounter,
        content_type=FHIR_JSON,
    )
    assert result.status_code == 201, result.json
    record_id = int(result.json["id"])
    own = client.get(f"{FHIR}/Condition/{record_id}", headers=tokens["patient"])
    assert own.status_code == 200
    assert own.json["encounter"]["reference"] == f"Encounter/{record_id}"
    assert own.json["code"]["coding"][0]["code"] == "M17.9"
    assert (
        client.get(f"{FHIR}/Condition/{record_id}", headers=tokens["other"]).status_code
        == 404
    )

    invoice = client.post(
        "/api/v1/invoices",
        headers=tokens["staff"],
        json={
            "patient_id": patient,
            "due_date": visit_date,
            "icd10_code": "M17.9",
            "items": [{"service_id": 1, "quantity": 1}],
        },
    )
    assert invoice.status_code == 201 and invoice.json["icd10_code"] == "M17.9"
    stats = client.get(
        f"/api/v1/reports/patients?start={visit_date}&end={visit_date}",
        headers=tokens["staff"],
    )
    assert stats.status_code == 200
    assert any(item["code"] == "M17.9" for item in stats.json["diagnoses"])
    with app.extensions["ortho_db"].connect() as connection:
        event = connection.scalar(
            select(audit_log.c.action).where(
                audit_log.c.resource == f"Encounter/{record_id}"
            )
        )
    assert event == "create"


def test_fhir_staff_write_and_patient_read_round_trip(client, tokens, people):
    patient, other, practitioner = people
    subject = {"reference": f"Patient/{patient}"}
    stranger = {"reference": f"Patient/{other}"}
    today = utcnow().date().isoformat()

    def create(kind, data, role="staff"):
        return client.post(
            f"{FHIR}/{kind}",
            headers=tokens[role],
            json={"resourceType": kind, **data},
            content_type=FHIR_JSON,
        )

    def saved(kind, data):
        result = create(kind, data)
        assert result.status_code == 201, result.json
        assert result.mimetype == FHIR_JSON
        identity = result.json["id"]
        assert result.headers["Location"].endswith(f"/{kind}/{identity}")
        patient_read = client.get(result.headers["Location"], headers=tokens["patient"])
        assert patient_read.status_code == 200 and patient_read.json == result.json
        assert (
            client.get(result.headers["Location"], headers=tokens["other"]).status_code
            == 404
        )
        return identity

    encounter = {
        "status": "finished",
        "class": {"code": "AMB"},
        "subject": subject,
        "period": {"start": today},
        "diagnosis": [{"condition": {"reference": "#diagnosis"}}],
        "participant": [{"individual": {"reference": f"Practitioner/{practitioner}"}}],
        "contained": [
            {
                "resourceType": "Condition",
                "id": "diagnosis",
                "subject": subject,
                "code": {"coding": [{"system": ICD10_SYSTEM, "code": "M25.5"}]},
            }
        ],
    }
    assert create("Encounter", encounter, role="patient").status_code == 403
    assert create("Encounter", encounter, role="admin").status_code == 403
    unrelated_condition = {**encounter["contained"][0], "subject": stranger}
    assert (
        create(
            "Encounter", {**encounter, "contained": [unrelated_condition]}
        ).status_code
        == 422
    )
    visit = saved("Encounter", encounter)
    condition = client.get(f"{FHIR}/Condition/{visit}", headers=tokens["patient"])
    assert condition.json["code"]["coding"][0]["code"] == "M25.5"

    prescription = {
        "status": "unknown",
        "intent": "order",
        "subject": subject,
        "encounter": {"reference": f"Encounter/{visit}"},
        "medicationCodeableConcept": {"text": "Fictional test medication"},
        "dosageInstruction": [{"text": "Fictional test instructions"}],
    }
    assert (
        create("MedicationRequest", {**prescription, "subject": stranger}).status_code
        == 422
    )
    saved("MedicationRequest", prescription)

    plan = saved(
        "CarePlan",
        {
            "status": "active",
            "intent": "plan",
            "subject": subject,
            "title": "Fictional recovery plan",
            "period": {"start": today},
        },
    )
    session = saved(
        "Procedure",
        {
            "status": "completed",
            "code": {"text": "Rehabilitation session"},
            "subject": subject,
            "basedOn": [{"reference": f"CarePlan/{plan}"}],
            "performedDateTime": today,
        },
    )
    pain = {
        "status": "final",
        "code": {"text": "Pain score (0 to 10)"},
        "subject": subject,
        "partOf": [{"reference": f"Procedure/{session}"}],
        "effectiveDateTime": today,
        "valueQuantity": {"value": 0, "unit": "score"},
    }
    assert (
        create("Observation", {**pain, "valueQuantity": {"value": 11}}).status_code
        == 422
    )
    assert saved("Observation", pain) == f"{session}-pain"
    assert create("Observation", pain).status_code == 409
    assert (
        saved(
            "Observation",
            {
                **pain,
                "code": {"text": "Range of motion"},
                "valueQuantity": {"value": 23.75, "code": "deg"},
            },
        )
        == f"{session}-rom"
    )

    expected = {
        "Appointment",
        "Encounter",
        "MedicationRequest",
        "CarePlan",
        "Procedure",
        "Observation",
    }
    for role, writable in (("staff", expected), ("admin", set())):
        capabilities = client.get(f"{FHIR}/metadata", headers=tokens[role]).json[
            "rest"
        ][0]["resource"]
        assert {
            item["type"]
            for item in capabilities
            if {"code": "create"} in item["interaction"]
        } == writable
    assert create("Invoice", {}).status_code == 405


def test_imaging_metadata_uid_and_review_visibility(app, client, tokens, people):
    patient, other, practitioner = people
    with app.extensions["ortho_db"].begin() as connection:
        study_id = connection.scalar(
            scan.insert()
            .values(
                patient_id=patient,
                study_uid="2.25.3200021",
                orthanc_id="fictional-demo-only",
                modality="DX",
                body_part="Knee",
                study_date=date(2026, 11, 18),
                uploaded_by=practitioner,
            )
            .returning(scan.c.scan_id)
        )
        report_ids = connection.scalars(
            cdss_result.insert()
            .values(
                [
                    {
                        "scan_id": study_id,
                        "model_version": "test",
                        "finding": "Fictional annotation",
                        "review_status": status,
                        "reviewed_by": practitioner if status != "pending" else None,
                    }
                    for status in ("accepted", "pending", "rejected")
                ]
            )
            .returning(cdss_result.c.result_id)
        ).all()

    for role in ("staff", "patient"):
        study = client.get(f"{FHIR}/ImagingStudy/{study_id}", headers=tokens[role])
        assert study.status_code == 200
        assert study.json["identifier"] == [
            {"system": "urn:dicom:uid", "value": "urn:oid:2.25.3200021"}
        ]
        assert "fictional-demo-only" not in study.get_data(as_text=True)
    assert (
        client.get(
            f"{FHIR}/ImagingStudy/{study_id}", headers=tokens["other"]
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"{FHIR}/ImagingStudy/{study_id}", headers=tokens["admin"]
        ).status_code
        == 403
    )
    for identity, status in zip(
        report_ids, ("final", "preliminary", "entered-in-error")
    ):
        report = client.get(
            f"{FHIR}/DiagnosticReport/{identity}", headers=tokens["staff"]
        )
        assert report.status_code == 200 and report.json["status"] == status
        assert report.json["imagingStudy"] == [
            {"reference": f"ImagingStudy/{study_id}"}
        ]
        own = client.get(
            f"{FHIR}/DiagnosticReport/{identity}", headers=tokens["patient"]
        )
        assert own.status_code == (200 if status == "final" else 404)
    listing = client.get(
        f"{FHIR}/DiagnosticReport?patient=Patient/{patient}", headers=tokens["patient"]
    )
    listed = {item["resource"]["id"] for item in listing.json["entry"]}
    assert str(report_ids[0]) in listed
    assert listed.isdisjoint(map(str, report_ids[1:]))
    assert (
        client.get(
            f"{FHIR}/DiagnosticReport?patient=Patient/{other}",
            headers=tokens["patient"],
        ).json["total"]
        == 0
    )
