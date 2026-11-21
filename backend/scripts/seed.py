"""Reproducible, fictional demo data. Run only with DEMO_MODE=1."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from secrets import token_urlsafe

import bcrypt
import click
from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.models.schema_v1 import (
    appointment,
    icd10_code,
    invoice,
    invoice_item,
    medical_record,
    patient,
    payment,
    prescription,
    rehab_session,
    service,
    staff,
    treatment_plan,
    user,
)
from app.utils.common import db, utcnow

ICD10_SAMPLE = (
    ("M17.9", "Gonarthrosis, unspecified", "Musculoskeletal"),
    ("M25.5", "Pain in joint", "Musculoskeletal"),
    ("M54.5", "Low back pain", "Musculoskeletal"),
    ("S52.5", "Fracture of lower end of radius", "Injury"),
)
ADMIN = "admin@ortho.example"
STAFF = "staff@ortho.example"
PATIENT = "patient@ortho.example"
OTHER = "patient2@ortho.example"


def install_command(app):
    @app.cli.command("seed-demo")
    def seed_command():
        if not current_app.config["DEMO_MODE"]:
            raise click.ClickException("Set DEMO_MODE=1 to load fictional examples.")
        created = seed(db())
        click.echo("Loaded demo data." if created else "Demo data already loaded.")


def insert_one(connection, table, **values):
    return connection.scalar(
        table.insert().values(**values).returning(next(iter(table.primary_key)))
    )


def seed(engine):
    with engine.begin() as connection:
        connection.execute(select(func.pg_advisory_xact_lock(320002)))
        connection.execute(
            insert(icd10_code)
            .values(
                [
                    {"code": code, "description": description, "category": category}
                    for code, description, category in ICD10_SAMPLE
                ]
            )
            .on_conflict_do_nothing(index_elements=[icd10_code.c.code])
        )
        if connection.scalar(select(user.c.user_id).where(user.c.email == ADMIN)):
            return False

        hashed = bcrypt.hashpw(token_urlsafe(32).encode(), bcrypt.gensalt()).decode()
        staff_account = None
        patients = []
        for email, role in (
            (ADMIN, "admin"),
            (STAFF, "staff"),
            (PATIENT, "patient"),
            (OTHER, "patient"),
        ):
            account = insert_one(
                connection, user, email=email, role=role, password_hash=hashed
            )
            if role == "staff":
                staff_account = account
            elif role == "patient":
                patients.append(account)
        clinician = insert_one(
            connection,
            staff,
            user_id=staff_account,
            full_name="Demo Clinician",
            specialty="Orthopedics",
            staff_type="doctor",
        )
        first = insert_one(
            connection,
            patient,
            user_id=patients[0],
            full_name="Nour Example",
            birth_date=date(1993, 3, 12),
            gender="female",
        )
        second = insert_one(
            connection,
            patient,
            user_id=patients[1],
            full_name="Karim Example",
            birth_date=date(1988, 6, 8),
            gender="male",
        )
        today = utcnow().date()
        service_ids = [
            insert_one(
                connection,
                service,
                name=name,
                description=summary,
                price=Decimal(price),
            )
            for name, summary, price in (
                ("Orthopedic consultation", "Outpatient assessment", "450.00"),
                ("Rehabilitation session", "Guided physiotherapy", "275.00"),
                ("Follow-up visit", "Review and follow-up", "325.00"),
            )
        ]

        for index, patient_id in enumerate((first, second)):
            visit = today - timedelta(days=9 - 4 * index)
            start = datetime.combine(visit, time(10), timezone.utc)
            encounter = insert_one(
                connection,
                appointment,
                patient_id=patient_id,
                staff_id=clinician,
                type="consultation",
                start_time=start,
                end_time=start + timedelta(minutes=30),
                status="completed",
            )
            next_start = datetime.combine(
                today + timedelta(days=index), time(15), timezone.utc
            )
            insert_one(
                connection,
                appointment,
                patient_id=patient_id,
                staff_id=clinician,
                type="therapy",
                start_time=next_start,
                end_time=next_start + timedelta(minutes=30),
            )
            code = ("M25.5", "M54.5")[index]
            record = insert_one(
                connection,
                medical_record,
                patient_id=patient_id,
                staff_id=clinician,
                visit_date=visit,
                chief_complaint="Fictional visit for demonstration",
                affected_area=("knee", "back")[index],
                icd10_code=code,
                diagnosis=("Pain in joint", "Low back pain")[index],
            )
            insert_one(
                connection,
                prescription,
                record_id=record,
                medication="Example medication",
                instructions="Fictional prescription for interface testing.",
            )
            plan = insert_one(
                connection,
                treatment_plan,
                patient_id=patient_id,
                staff_id=clinician,
                title="Mobility follow-up",
                start_date=visit,
                goal="Record example mobility results.",
            )
            insert_one(
                connection,
                rehab_session,
                plan_id=plan,
                session_date=visit + timedelta(days=1),
                exercises="Example supervised session",
                pain_score=3,
                range_of_motion=Decimal("105.00"),
            )
            bill = insert_one(
                connection,
                invoice,
                patient_id=patient_id,
                appointment_id=encounter,
                icd10_code=code,
                issue_date=visit,
                due_date=today + timedelta(days=14),
                total_amount=Decimal("450.00"),
                status="partial" if index else "unpaid",
            )
            insert_one(
                connection,
                invoice_item,
                invoice_id=bill,
                service_id=service_ids[0],
                quantity=1,
                unit_price=Decimal("450.00"),
            )
            if index:
                insert_one(
                    connection,
                    payment,
                    invoice_id=bill,
                    amount=Decimal("150.00"),
                    method="cash",
                    status="success",
                    paid_at=start + timedelta(hours=1),
                )
    return True


def main():
    from app import create_app

    app = create_app(demo=True)
    with app.app_context():
        created = seed(db())
    print("Loaded demo data." if created else "Demo data already loaded.")


if __name__ == "__main__":
    main()
