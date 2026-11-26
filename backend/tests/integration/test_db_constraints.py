"""PostgreSQL DDL constraint tests (ON DELETE RESTRICT, CHECK, and GiST overlap)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import Patient, Service, metadata


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

    for table in expected_tables:
        for fk in inspector.get_foreign_keys(table):
            assert (
                fk.get("options", {}).get("ondelete") == "RESTRICT"
            ), f"Table {table} FK {fk['name']} missing ON DELETE RESTRICT"

    patient_id, _, staff_id = people

    with engine.begin() as conn:
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(
                Patient.__table__.delete().where(Patient.patient_id == patient_id)
            )

        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(
                text(
                    'INSERT INTO "user" (email, password_hash, role, is_active) '
                    "VALUES ('badrole@hcis.test', 'hash', 'guest', true)"
                )
            )

        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(
                Service.__table__.insert().values(
                    name="Invalid Negative Service",
                    price=Decimal("-5.00"),
                    is_active=True,
                )
            )

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

    for stmt in (
        "UPDATE audit_log SET action = 'mutated'",
        "DELETE FROM audit_log",
        "TRUNCATE audit_log",
    ):
        with pytest.raises(DBAPIError) as exc, engine.begin() as conn:
            conn.execute(text(stmt))
        assert exc.value.orig.sqlstate == "55000"
