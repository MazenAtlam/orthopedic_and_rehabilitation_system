"""Immutable initial schema. New schema changes require a new Alembic revision."""

from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Identity,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()
MONEY = Numeric(10, 2)
UTC_TIME = DateTime(timezone=True)


def pk(name: str) -> Column[Any]:
    return Column(name, Integer, Identity(), primary_key=True)


def fk(
    name: str,
    target: str,
    *,
    optional: bool = False,
    unique: bool = False,
    index: bool = False,
) -> Column[Any]:
    return Column(
        name,
        Integer,
        ForeignKey(target, ondelete="RESTRICT"),
        nullable=optional,
        unique=unique,
        index=index,
    )


def choice(
    name: str, table: str, *values: str, default: str | None = None
) -> Column[Any]:
    return Column(
        name,
        Enum(
            *values,
            name=f"{table}_{name}_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        server_default=default,
    )


def created(name: str = "created_at") -> Column[Any]:
    return Column(name, UTC_TIME, nullable=False, server_default=func.now())


user = Table(
    "user",
    metadata,
    pk("user_id"),
    Column("email", String(255), unique=True, nullable=False),
    Column("password_hash", String(255), nullable=False),
    choice("role", "user", "admin", "staff", "patient"),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    created(),
)
patient = Table(
    "patient",
    metadata,
    pk("patient_id"),
    fk("user_id", "user.user_id", unique=True),
    Column("full_name", String(150), nullable=False),
    Column("birth_date", Date, nullable=False),
    choice("gender", "patient", "male", "female", "other", "unknown"),
    Column("phone", String(20)),
    Column("address", Text),
    Column("national_id", String(20)),
    Column("emergency_contact", String(150)),
)
staff = Table(
    "staff",
    metadata,
    pk("staff_id"),
    fk("user_id", "user.user_id", unique=True),
    Column("full_name", String(150), nullable=False),
    choice("staff_type", "staff", "doctor", "physiotherapist", "radiologist", "nurse"),
    Column("specialty", String(100)),
    Column("license_no", String(50)),
    Column("phone", String(20)),
)
appointment = Table(
    "appointment",
    metadata,
    pk("appointment_id"),
    fk("patient_id", "patient.patient_id", index=True),
    fk("staff_id", "staff.staff_id", index=True),
    choice("type", "appointment", "consultation", "therapy", "imaging"),
    Column("start_time", UTC_TIME, nullable=False, index=True),
    Column("end_time", UTC_TIME, nullable=False),
    choice(
        "status",
        "appointment",
        "booked",
        "completed",
        "cancelled",
        "no_show",
        default="booked",
    ),
    Column("notes", Text),
    CheckConstraint("end_time > start_time", name="appointment_end_after_start"),
)
icd10_code = Table(
    "icd10_code",
    metadata,
    Column("code", String(10), primary_key=True),
    Column("description", String(255), nullable=False),
    Column("category", String(100), nullable=False),
)


def diagnosis_code(*, optional: bool = False) -> Column[Any]:
    return Column(
        "icd10_code",
        String(10),
        ForeignKey("icd10_code.code", ondelete="RESTRICT"),
        nullable=optional,
    )


medical_record = Table(
    "medical_record",
    metadata,
    pk("record_id"),
    fk("patient_id", "patient.patient_id", index=True),
    fk("staff_id", "staff.staff_id", index=True),
    Column("visit_date", Date, nullable=False),
    Column("chief_complaint", Text),
    Column("affected_area", String(100)),
    Column("diagnosis", Text),
    diagnosis_code(),
    Column("notes", Text),
)
prescription = Table(
    "prescription",
    metadata,
    pk("prescription_id"),
    fk("record_id", "medical_record.record_id", index=True),
    Column("medication", String(150), nullable=False),
    Column("dose", String(50)),
    Column("frequency", String(50)),
    Column("duration", String(50)),
    Column("instructions", Text),
)
treatment_plan = Table(
    "treatment_plan",
    metadata,
    pk("plan_id"),
    fk("patient_id", "patient.patient_id", index=True),
    fk("staff_id", "staff.staff_id", index=True),
    Column("title", String(150), nullable=False),
    Column("goal", Text),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date),
    choice(
        "status", "treatment_plan", "active", "completed", "stopped", default="active"
    ),
    CheckConstraint("end_date >= start_date", name="plan_dates_in_order"),
)
rehab_session = Table(
    "rehab_session",
    metadata,
    pk("session_id"),
    fk("plan_id", "treatment_plan.plan_id", index=True),
    fk("appointment_id", "appointment.appointment_id", optional=True, unique=True),
    Column("session_date", Date, nullable=False),
    Column("exercises", Text),
    Column("pain_score", SmallInteger),
    Column("range_of_motion", Numeric(6, 2)),
    Column("notes", Text),
    CheckConstraint("pain_score BETWEEN 0 AND 10", name="rehab_session_pain_0_to_10"),
    CheckConstraint("range_of_motion >= 0", name="rehab_session_motion_nonnegative"),
)
scan = Table(
    "scan",
    metadata,
    pk("scan_id"),
    fk("patient_id", "patient.patient_id", index=True),
    fk("record_id", "medical_record.record_id", optional=True),
    Column("study_uid", String(128), nullable=False, unique=True),
    Column("orthanc_id", String(64), nullable=False),
    Column("modality", String(10)),
    Column("body_part", String(50)),
    Column("study_date", Date),
    fk("uploaded_by", "staff.staff_id"),
    created("uploaded_at"),
)
cdss_result = Table(
    "cdss_result",
    metadata,
    pk("result_id"),
    fk("scan_id", "scan.scan_id", index=True),
    Column("model_version", String(50), nullable=False),
    Column("finding", String(150)),
    Column("confidence", Float(precision=24)),
    Column("report_text", Text),
    choice(
        "review_status",
        "cdss_result",
        "pending",
        "accepted",
        "rejected",
        default="pending",
    ),
    fk("reviewed_by", "staff.staff_id", optional=True),
    created(),
    CheckConstraint("confidence BETWEEN 0 AND 1", name="cdss_confidence_0_to_1"),
)
annotation = Table(
    "annotation",
    metadata,
    pk("annotation_id"),
    fk("scan_id", "scan.scan_id", index=True),
    fk("created_by", "staff.staff_id"),
    choice("type", "annotation", "arrow", "length", "angle", "note"),
    Column("data", JSONB, nullable=False),
    Column("note", Text),
    created(),
)
service = Table(
    "service",
    metadata,
    pk("service_id"),
    Column("name", String(150), nullable=False),
    Column("description", Text),
    Column("price", MONEY, nullable=False),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    CheckConstraint("price >= 0", name="service_price_nonnegative"),
)
invoice = Table(
    "invoice",
    metadata,
    pk("invoice_id"),
    fk("patient_id", "patient.patient_id", index=True),
    fk("appointment_id", "appointment.appointment_id", optional=True, index=True),
    diagnosis_code(optional=True),
    Column("issue_date", Date, nullable=False, index=True),
    Column("due_date", Date, nullable=False),
    Column("total_amount", MONEY, nullable=False),
    choice(
        "status", "invoice", "unpaid", "partial", "paid", "cancelled", default="unpaid"
    ),
    CheckConstraint("due_date >= issue_date", name="invoice_dates_in_order"),
    CheckConstraint("total_amount >= 0", name="invoice_total_nonnegative"),
)
invoice_item = Table(
    "invoice_item",
    metadata,
    pk("item_id"),
    fk("invoice_id", "invoice.invoice_id", index=True),
    fk("service_id", "service.service_id"),
    Column("quantity", Integer, nullable=False),
    Column("unit_price", MONEY, nullable=False),
    CheckConstraint("quantity >= 1", name="invoice_item_positive_quantity"),
    CheckConstraint("unit_price >= 0", name="invoice_item_price_nonnegative"),
)
payment = Table(
    "payment",
    metadata,
    pk("payment_id"),
    fk("invoice_id", "invoice.invoice_id", index=True),
    Column("amount", MONEY, nullable=False),
    choice("method", "payment", "cash", "card", "online"),
    choice("status", "payment", "pending", "success", "failed"),
    Column("paid_at", UTC_TIME, index=True),
    Column("idempotency_key", String(128)),
    UniqueConstraint(
        "invoice_id", "idempotency_key", name="payment_invoice_request_once"
    ),
    CheckConstraint("amount > 0", name="payment_amount_positive"),
    CheckConstraint(
        "status <> 'success' OR paid_at IS NOT NULL", name="payment_success_date"
    ),
)
audit_log = Table(
    "audit_log",
    metadata,
    pk("log_id"),
    fk("user_id", "user.user_id", index=True),
    Column("action", String(50), nullable=False),
    Column("resource", String(100), nullable=False),
    Column("ip_address", String(45)),
    created(),
)
