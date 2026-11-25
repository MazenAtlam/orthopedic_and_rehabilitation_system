"""Reproducible, fictional demo data. Run only with DEMO_MODE=1."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

import bcrypt
import click
from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.models import (
    Appointment,
    AppointmentStatus,
    AppointmentType,
    Gender,
    Icd10Code,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    MedicalRecord,
    Patient,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Prescription,
    RehabSession,
    Scan,
    Service,
    Staff,
    StaffType,
    TreatmentPlan,
    User,
    UserRole,
)
from app.services.imaging import (
    record_annotation,
    record_cdss_result,
    register_study,
    review_cdss_result,
)
from app.utils.common import db, utcnow

ICD10_SAMPLE = (
    ("M17.9", "Gonarthrosis, unspecified", "Musculoskeletal"),
    ("M25.5", "Pain in joint", "Musculoskeletal"),
    ("M54.5", "Low back pain", "Musculoskeletal"),
    ("S52.5", "Fracture of lower end of radius", "Injury"),
)
ADMIN = "admin@hcis.test"
STAFF = "doctor1@hcis.test"
PHYSIO = "physio1@hcis.test"
PATIENT = "patient1@hcis.test"
OTHER = "patient2@hcis.test"
THIRD = "patient3@hcis.test"
DEMO_PASSWORD = "Test@12345"
DEMO_ACCOUNTS = {
    ADMIN: "admin",
    STAFF: "staff",
    PHYSIO: "staff",
    PATIENT: "patient",
    OTHER: "patient",
    THIRD: "patient",
}
DEMO_STUDY_UID = "2.25.213338814091244823214794205785473106552"


def install_command(app: Any) -> None:
    @app.cli.command("seed-demo")
    def seed_command() -> None:
        load_demo()


def insert_one(connection: Any, model: Any, **values: Any) -> Any:
    table = model.__table__
    return connection.scalar(
        table.insert().values(**values).returning(next(iter(table.primary_key)))
    )


def seed_imaging_example(connection: Any) -> bool:
    if connection.scalar(select(Scan.scan_id).where(Scan.study_uid == DEMO_STUDY_UID)):
        return False
    actor = connection.scalar(
        select(User.user_id).where(
            User.email == STAFF,
            User.is_active.is_(True),
            User.role == UserRole.staff,
        )
    )
    visit = (
        connection.execute(
            select(
                MedicalRecord.record_id,
                MedicalRecord.patient_id,
                MedicalRecord.visit_date,
            )
            .select_from(
                MedicalRecord.__table__.join(
                    Patient.__table__, MedicalRecord.patient_id == Patient.patient_id
                ).join(User.__table__, Patient.user_id == User.user_id)
            )
            .where(
                User.email == PATIENT,
                User.role == UserRole.patient,
            )
            .order_by(MedicalRecord.record_id)
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )
    if actor is None or visit is None:
        return False
    study = register_study(
        connection,
        int(actor),
        {
            "patient_id": visit["patient_id"],
            "record_id": visit["record_id"],
            "study_uid": DEMO_STUDY_UID,
            "orthanc_id": "fictional-studystore-entry",
            "modality": "DX",
            "body_part": "Knee",
            "study_date": visit["visit_date"].isoformat(),
        },
    )
    scan_id = study["scan_id"]
    approved = record_cdss_result(
        connection,
        int(actor),
        scan_id,
        {
            "model_version": "demo-fixture-v1",
            "report_text": (
                "Fictional accepted finding for the integration demonstration."
            ),
            "confidence": 0.92,
        },
    )
    review_cdss_result(connection, int(actor), approved["result_id"], "accepted")
    record_cdss_result(
        connection,
        int(actor),
        scan_id,
        {
            "model_version": "demo-fixture-v1",
            "report_text": "Fictional preliminary finding awaiting staff review.",
        },
    )
    record_annotation(
        connection,
        int(actor),
        scan_id,
        {
            "type": "note",
            "data": {"text": "Example annotation for the fictional study."},
        },
    )
    return True


def seed(engine: Any) -> bool:
    if (
        not current_app.config.get("DEMO_MODE")
        or current_app.config.get("APP_ENV") == "production"
    ):
        raise click.ClickException("Seed requires a non-production DEMO_MODE=1 app.")
    with engine.begin() as connection:
        connection.execute(select(func.pg_advisory_xact_lock(320002)))
        connection.execute(
            insert(Icd10Code)
            .values(
                [
                    {"code": code, "description": description, "category": category}
                    for code, description, category in ICD10_SAMPLE
                ]
            )
            .on_conflict_do_nothing(index_elements=[Icd10Code.code])
        )
        raw_accounts = (
            connection.execute(
                select(User.email, User.role).where(User.email.in_(DEMO_ACCOUNTS))
            )
            .tuples()
            .all()
        )
        accounts = {
            email: (role.value if isinstance(role, Enum) else str(role))
            for email, role in raw_accounts
        }
        if accounts == DEMO_ACCOUNTS:
            return seed_imaging_example(connection)
        if accounts:
            raise click.ClickException(
                "Some demo emails already exist. Use a separate, fresh demo database."
            )
        ids = {
            email: insert_one(
                connection,
                User,
                email=email,
                role=UserRole(role),
                password_hash=bcrypt.hashpw(
                    DEMO_PASSWORD.encode(), bcrypt.gensalt()
                ).decode(),
            )
            for email, role in DEMO_ACCOUNTS.items()
        }
        clinician = insert_one(
            connection,
            Staff,
            user_id=ids[STAFF],
            full_name="Demo Clinician",
            specialty="Orthopedics",
            staff_type=StaffType.doctor,
        )
        insert_one(
            connection,
            Staff,
            user_id=ids[PHYSIO],
            full_name="Demo Physiotherapist",
            specialty="Rehabilitation",
            staff_type=StaffType.physiotherapist,
        )
        first = insert_one(
            connection,
            Patient,
            user_id=ids[PATIENT],
            full_name="Nour Example",
            birth_date=date(1993, 3, 12),
            gender=Gender.female,
        )
        second = insert_one(
            connection,
            Patient,
            user_id=ids[OTHER],
            full_name="Karim Example",
            birth_date=date(1988, 6, 8),
            gender=Gender.male,
        )
        insert_one(
            connection,
            Patient,
            user_id=ids[THIRD],
            full_name="Salma Example",
            birth_date=date(1996, 7, 15),
            gender=Gender.female,
        )
        today = utcnow().date()
        service_ids = {
            name: insert_one(
                connection,
                Service,
                name=name,
                description=summary,
                price=Decimal(price),
            )
            for name, summary, price in (
                ("Consultation", "Outpatient assessment", "300.00"),
                ("Physio session", "Guided physiotherapy", "250.00"),
                ("X-ray imaging", "Orthopedic imaging", "400.00"),
            )
        }

        for index, patient_id in enumerate((first, second)):
            visit = today - timedelta(days=9 - 4 * index)
            start = datetime.combine(visit, time(10), timezone.utc)
            encounter = insert_one(
                connection,
                Appointment,
                patient_id=patient_id,
                staff_id=clinician,
                type=AppointmentType.consultation,
                start_time=start,
                end_time=start + timedelta(minutes=30),
                status=AppointmentStatus.completed,
            )
            next_start = datetime.combine(
                today + timedelta(days=1 + index), time(10), timezone.utc
            )
            insert_one(
                connection,
                Appointment,
                patient_id=patient_id,
                staff_id=clinician,
                type=AppointmentType.therapy,
                start_time=next_start,
                end_time=next_start + timedelta(minutes=30),
            )
            code = ("M25.5", "M54.5")[index]
            record = insert_one(
                connection,
                MedicalRecord,
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
                Prescription,
                record_id=record,
                medication="Example medication",
                instructions="Fictional prescription for interface testing.",
            )
            plan = insert_one(
                connection,
                TreatmentPlan,
                patient_id=patient_id,
                staff_id=clinician,
                title="Mobility follow-up",
                start_date=visit,
                goal="Record example mobility results.",
            )
            insert_one(
                connection,
                RehabSession,
                plan_id=plan,
                session_date=visit + timedelta(days=1),
                exercises="Example supervised session",
                pain_score=3,
                range_of_motion=Decimal("105.00"),
            )
            service_name, price, quantity = (
                ("Consultation", Decimal("300.00"), 1)
                if index
                else ("Physio session", Decimal("250.00"), 2)
            )
            bill = insert_one(
                connection,
                Invoice,
                patient_id=patient_id,
                appointment_id=encounter,
                icd10_code=code,
                issue_date=visit,
                due_date=today + timedelta(days=14),
                total_amount=price * quantity,
                status=InvoiceStatus.partial if index else InvoiceStatus.unpaid,
            )
            insert_one(
                connection,
                InvoiceItem,
                invoice_id=bill,
                service_id=service_ids[service_name],
                quantity=quantity,
                unit_price=price,
            )
            if index:
                insert_one(
                    connection,
                    Payment,
                    invoice_id=bill,
                    amount=Decimal("150.00"),
                    method=PaymentMethod.cash,
                    status=PaymentStatus.success,
                    paid_at=start + timedelta(hours=1),
                )
        seed_imaging_example(connection)
    return True


def load_demo() -> None:
    created = seed(db())
    click.echo("Loaded demo data." if created else "Demo data already loaded.")


def main() -> None:
    from app import create_app

    app = create_app(demo=True)
    with app.app_context():
        try:
            load_demo()
        except click.ClickException as error:
            error.show()
            raise SystemExit(error.exit_code) from None


if __name__ == "__main__":
    main()
