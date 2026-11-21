from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.utils.common import ApiError
from app.services.imaging import (
    record_annotation,
    record_cdss_result,
    register_study,
    review_cdss_result,
)
from app.models.schema_v1 import audit_log, cdss_result, medical_record, scan, user
from scripts.seed import ADMIN, DEMO_STUDY_UID, PATIENT, STAFF

FHIR = "/api/v1/fhir"


@pytest.fixture
def integration(app, people):
    engine = app.extensions["ortho_db"]
    with engine.connect() as connection:
        accounts = dict(
            connection.execute(select(user.c.email, user.c.user_id)).tuples().all()
        )
        visit = connection.scalar(
            select(medical_record.c.record_id)
            .where(
                medical_record.c.patient_id == people[0],
            )
            .order_by(medical_record.c.record_id)
        )
    return (
        engine,
        accounts,
        {
            "patient_id": people[0],
            "record_id": visit,
            "study_uid": "2.25.3200022",
            "orthanc_id": "internal-test-locator",
            "modality": "DX",
            "body_part": "Knee",
            "study_date": "2026-11-19",
        },
    )


def assert_error(status, action, *args):
    with pytest.raises(ApiError) as error:
        action(*args)
    assert error.value.status == status


def test_study_registration_and_staff_identity(integration, people):
    engine, accounts, payload = integration
    with engine.begin() as connection:
        for account in (PATIENT, ADMIN):
            assert_error(403, register_study, connection, accounts[account], payload)
        assert_error(
            422,
            register_study,
            connection,
            accounts[STAFF],
            {**payload, "study_uid": "1.02.3"},
        )
        assert_error(
            422,
            register_study,
            connection,
            accounts[STAFF],
            {**payload, "patient_id": people[1]},
        )
        study = register_study(connection, accounts[STAFF], payload)
        assert study["uploaded_by"] == people[2]
        assert register_study(connection, accounts[STAFF], payload) == study
        assert_error(
            409,
            register_study,
            connection,
            accounts[STAFF],
            {
                **payload,
                "patient_id": people[1],
                "record_id": None,
            },
        )
        action_count = connection.scalar(
            select(func.count())
            .select_from(audit_log)
            .where(
                audit_log.c.action == "imaging.study.register",
                audit_log.c.resource == f"scan/{study['scan_id']}",
            )
        )
        assert action_count == 1


def test_cdss_review_updates_fhir_visibility(integration, client, tokens, people):
    engine, accounts, payload = integration
    actor = accounts[STAFF]
    with engine.begin() as connection:
        study = register_study(
            connection, actor, {**payload, "study_uid": "2.25.3200023"}
        )
        finding = {"model_version": "test-2", "finding": "Fictional test result"}
        assert_error(
            422,
            record_cdss_result,
            connection,
            actor,
            study["scan_id"],
            {
                **finding,
                "confidence": Decimal("NaN"),
            },
        )
        result = record_cdss_result(
            connection, actor, study["scan_id"], {**finding, "confidence": 0.5}
        )
    path = f"{FHIR}/DiagnosticReport/{result['result_id']}"
    assert client.get(path, headers=tokens["staff"]).json["status"] == "preliminary"
    assert client.get(path, headers=tokens["patient"]).status_code == 404

    with engine.begin() as connection:
        assert_error(
            403,
            review_cdss_result,
            connection,
            accounts[PATIENT],
            result["result_id"],
            "accepted",
        )
        reviewed = review_cdss_result(
            connection, actor, result["result_id"], "accepted"
        )
        assert reviewed["reviewed_by"] == people[2]
        assert (
            review_cdss_result(connection, actor, result["result_id"], "accepted")
            == reviewed
        )
        assert_error(
            409, review_cdss_result, connection, actor, result["result_id"], "rejected"
        )
    report = client.get(path, headers=tokens["patient"])
    assert report.status_code == 200 and report.json["status"] == "final"
    assert report.json["encounter"]["reference"] == f"Encounter/{payload['record_id']}"
    assert report.json["imagingStudy"] == [
        {"reference": f"ImagingStudy/{study['scan_id']}"}
    ]
    assert client.get(path, headers=tokens["other"]).status_code == 404
    assert client.get(path, headers=tokens["admin"]).status_code == 403


def test_annotation_and_audit_commit_together(integration, people):
    engine, accounts, payload = integration
    actor = accounts[STAFF]
    with engine.begin() as connection:
        study = register_study(
            connection, actor, {**payload, "study_uid": "2.25.3200024"}
        )
        scan_id = study["scan_id"]
        assert_error(
            422,
            record_annotation,
            connection,
            actor,
            scan_id,
            {"type": "length", "data": []},
        )
        saved = record_annotation(
            connection,
            actor,
            scan_id,
            {
                "type": "length",
                "data": {"millimetres": Decimal("12.5")},
                "note": "Fictional note",
            },
        )
        assert saved["data"]["millimetres"] == 12.5 and saved["created_by"] == people[2]
        log = (
            connection.execute(
                select(audit_log).where(
                    audit_log.c.resource == f"annotation/{saved['annotation_id']}",
                )
            )
            .mappings()
            .one()
        )
        assert log["action"] == "imaging.annotation.record" and log["user_id"] == actor
        assert "Fictional note" not in str(log)

    with pytest.raises(RuntimeError), engine.begin() as connection:
        reverted = record_annotation(
            connection, actor, scan_id, {"type": "note", "data": {}}
        )
        raise RuntimeError("Simulate adapter rollback")
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(audit_log.c.log_id).where(
                    audit_log.c.resource == f"annotation/{reverted['annotation_id']}",
                )
            )
            is None
        )


def test_database_enforces_study_and_review_relationships(integration, people):
    engine, accounts, payload = integration
    with engine.begin() as connection:
        study = register_study(
            connection, accounts[STAFF], {**payload, "study_uid": "2.25.3200025"}
        )
        with (
            pytest.raises(IntegrityError, match="scan_record_patient_fk"),
            connection.begin_nested(),
        ):
            connection.execute(
                scan.update()
                .where(scan.c.scan_id == study["scan_id"])
                .values(patient_id=people[1])
            )
        with (
            pytest.raises(IntegrityError, match="cdss_review_has_reviewer"),
            connection.begin_nested(),
        ):
            connection.execute(
                cdss_result.insert().values(
                    scan_id=study["scan_id"],
                    model_version="test-2",
                    review_status="accepted",
                )
            )


def test_demo_study_remains_unique(integration):
    engine, _, _ = integration
    with engine.connect() as connection:
        identity = connection.execute(
            select(scan.c.scan_id).where(
                scan.c.study_uid == DEMO_STUDY_UID,
            )
        ).scalar_one()
        states = connection.scalars(
            select(cdss_result.c.review_status).where(
                cdss_result.c.scan_id == identity,
            )
        ).all()
    assert sorted(states) == ["accepted", "pending"]
