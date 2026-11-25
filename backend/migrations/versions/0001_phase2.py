"""Initial Phase 1 schema for the Phase 2 healthcare prototype."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_phase2"
down_revision = None

MONEY = sa.Numeric(10, 2)
UTC_TIME = sa.DateTime(timezone=True)


def _pk(name: str) -> sa.Column:
    return sa.Column(name, sa.Integer(), sa.Identity(), primary_key=True)


def _fk(
    name: str, target: str, *, optional: bool = False, unique: bool = False
) -> sa.Column:
    return sa.Column(
        name,
        sa.Integer(),
        sa.ForeignKey(target, ondelete="RESTRICT"),
        nullable=optional,
        unique=unique,
    )


def _choice(
    name: str, table: str, *values: str, default: str | None = None
) -> sa.Column:
    return sa.Column(
        name,
        sa.Enum(
            *values,
            name=f"{table}_{name}_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        server_default=default,
    )


def _created(name: str = "created_at") -> sa.Column:
    return sa.Column(name, UTC_TIME, nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "user",
        _pk("user_id"),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        _choice("role", "user", "admin", "staff", "patient"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        _created(),
    )
    op.create_table(
        "icd10_code",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
    )
    op.create_table(
        "service",
        _pk("service_id"),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("price", MONEY, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.CheckConstraint("price >= 0", name="service_price_nonnegative"),
    )
    op.create_table(
        "audit_log",
        _pk("log_id"),
        _fk("user_id", "user.user_id"),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("ip_address", sa.String(45)),
        _created(),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])

    op.create_table(
        "patient",
        _pk("patient_id"),
        _fk("user_id", "user.user_id", unique=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        _choice("gender", "patient", "male", "female", "other", "unknown"),
        sa.Column("phone", sa.String(20)),
        sa.Column("address", sa.Text()),
        sa.Column("national_id", sa.String(20)),
        sa.Column("emergency_contact", sa.String(150)),
    )
    op.create_table(
        "staff",
        _pk("staff_id"),
        _fk("user_id", "user.user_id", unique=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        _choice(
            "staff_type", "staff", "doctor", "physiotherapist", "radiologist", "nurse"
        ),
        sa.Column("specialty", sa.String(100)),
        sa.Column("license_no", sa.String(50)),
        sa.Column("phone", sa.String(20)),
    )
    op.create_table(
        "appointment",
        _pk("appointment_id"),
        _fk("patient_id", "patient.patient_id"),
        _fk("staff_id", "staff.staff_id"),
        _choice("type", "appointment", "consultation", "therapy", "imaging"),
        sa.Column("start_time", UTC_TIME, nullable=False),
        sa.Column("end_time", UTC_TIME, nullable=False),
        _choice(
            "status",
            "appointment",
            "booked",
            "completed",
            "cancelled",
            "no_show",
            default="booked",
        ),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint("end_time > start_time", name="appointment_end_after_start"),
    )
    op.create_index("ix_appointment_patient_id", "appointment", ["patient_id"])
    op.create_index("ix_appointment_staff_id", "appointment", ["staff_id"])
    op.create_index("ix_appointment_start_time", "appointment", ["start_time"])

    op.create_table(
        "medical_record",
        _pk("record_id"),
        _fk("patient_id", "patient.patient_id"),
        _fk("staff_id", "staff.staff_id"),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("chief_complaint", sa.Text()),
        sa.Column("affected_area", sa.String(100)),
        sa.Column("diagnosis", sa.Text()),
        sa.Column(
            "icd10_code",
            sa.String(10),
            sa.ForeignKey("icd10_code.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text()),
    )
    op.create_index("ix_medical_record_patient_id", "medical_record", ["patient_id"])
    op.create_index("ix_medical_record_staff_id", "medical_record", ["staff_id"])

    op.create_table(
        "treatment_plan",
        _pk("plan_id"),
        _fk("patient_id", "patient.patient_id"),
        _fk("staff_id", "staff.staff_id"),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("goal", sa.Text()),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        _choice(
            "status",
            "treatment_plan",
            "active",
            "completed",
            "stopped",
            default="active",
        ),
        sa.CheckConstraint("end_date >= start_date", name="plan_dates_in_order"),
    )
    op.create_index("ix_treatment_plan_patient_id", "treatment_plan", ["patient_id"])
    op.create_index("ix_treatment_plan_staff_id", "treatment_plan", ["staff_id"])

    op.create_table(
        "prescription",
        _pk("prescription_id"),
        _fk("record_id", "medical_record.record_id"),
        sa.Column("medication", sa.String(150), nullable=False),
        sa.Column("dose", sa.String(50)),
        sa.Column("frequency", sa.String(50)),
        sa.Column("duration", sa.String(50)),
        sa.Column("instructions", sa.Text()),
    )
    op.create_index("ix_prescription_record_id", "prescription", ["record_id"])

    op.create_table(
        "rehab_session",
        _pk("session_id"),
        _fk("plan_id", "treatment_plan.plan_id"),
        _fk("appointment_id", "appointment.appointment_id", optional=True, unique=True),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("exercises", sa.Text()),
        sa.Column("pain_score", sa.SmallInteger()),
        sa.Column("range_of_motion", sa.Numeric(6, 2)),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint(
            "pain_score BETWEEN 0 AND 10", name="rehab_session_pain_0_to_10"
        ),
        sa.CheckConstraint(
            "range_of_motion >= 0", name="rehab_session_motion_nonnegative"
        ),
    )
    op.create_index("ix_rehab_session_plan_id", "rehab_session", ["plan_id"])

    op.create_table(
        "scan",
        _pk("scan_id"),
        _fk("patient_id", "patient.patient_id"),
        _fk("record_id", "medical_record.record_id", optional=True),
        sa.Column("study_uid", sa.String(128), nullable=False, unique=True),
        sa.Column("orthanc_id", sa.String(64), nullable=False),
        sa.Column("modality", sa.String(10)),
        sa.Column("body_part", sa.String(50)),
        sa.Column("study_date", sa.Date()),
        _fk("uploaded_by", "staff.staff_id"),
        _created("uploaded_at"),
    )
    op.create_index("ix_scan_patient_id", "scan", ["patient_id"])

    op.create_table(
        "invoice",
        _pk("invoice_id"),
        _fk("patient_id", "patient.patient_id"),
        _fk("appointment_id", "appointment.appointment_id", optional=True),
        sa.Column(
            "icd10_code",
            sa.String(10),
            sa.ForeignKey("icd10_code.code", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("total_amount", MONEY, nullable=False),
        _choice(
            "status",
            "invoice",
            "unpaid",
            "partial",
            "paid",
            "cancelled",
            default="unpaid",
        ),
        sa.CheckConstraint("due_date >= issue_date", name="invoice_dates_in_order"),
        sa.CheckConstraint("total_amount >= 0", name="invoice_total_nonnegative"),
    )
    op.create_index("ix_invoice_patient_id", "invoice", ["patient_id"])
    op.create_index("ix_invoice_appointment_id", "invoice", ["appointment_id"])
    op.create_index("ix_invoice_issue_date", "invoice", ["issue_date"])

    op.create_table(
        "cdss_result",
        _pk("result_id"),
        _fk("scan_id", "scan.scan_id"),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("finding", sa.String(150)),
        sa.Column("confidence", sa.Float(precision=24)),
        sa.Column("report_text", sa.Text()),
        _choice(
            "review_status",
            "cdss_result",
            "pending",
            "accepted",
            "rejected",
            default="pending",
        ),
        _fk("reviewed_by", "staff.staff_id", optional=True),
        _created(),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1", name="cdss_confidence_0_to_1"
        ),
    )
    op.create_index("ix_cdss_result_scan_id", "cdss_result", ["scan_id"])

    op.create_table(
        "annotation",
        _pk("annotation_id"),
        _fk("scan_id", "scan.scan_id"),
        _fk("created_by", "staff.staff_id"),
        _choice("type", "annotation", "arrow", "length", "angle", "note"),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("note", sa.Text()),
        _created(),
    )
    op.create_index("ix_annotation_scan_id", "annotation", ["scan_id"])

    op.create_table(
        "invoice_item",
        _pk("item_id"),
        _fk("invoice_id", "invoice.invoice_id"),
        _fk("service_id", "service.service_id"),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", MONEY, nullable=False),
        sa.CheckConstraint("quantity >= 1", name="invoice_item_positive_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="invoice_item_price_nonnegative"),
    )
    op.create_index("ix_invoice_item_invoice_id", "invoice_item", ["invoice_id"])

    op.create_table(
        "payment",
        _pk("payment_id"),
        _fk("invoice_id", "invoice.invoice_id"),
        sa.Column("amount", MONEY, nullable=False),
        _choice("method", "payment", "cash", "card", "online"),
        _choice("status", "payment", "pending", "success", "failed"),
        sa.Column("paid_at", UTC_TIME),
        sa.Column("idempotency_key", sa.String(128)),
        sa.UniqueConstraint(
            "invoice_id", "idempotency_key", name="payment_invoice_request_once"
        ),
        sa.CheckConstraint("amount > 0", name="payment_amount_positive"),
        sa.CheckConstraint(
            "status <> 'success' OR paid_at IS NOT NULL", name="payment_success_date"
        ),
    )
    op.create_index("ix_payment_invoice_id", "payment", ["invoice_id"])
    op.create_index("ix_payment_paid_at", "payment", ["paid_at"])

    op.execute(
        """
        ALTER TABLE appointment ADD CONSTRAINT appointment_staff_no_overlap
        EXCLUDE USING gist
        (staff_id WITH =, tstzrange(start_time, end_time, '[)') WITH &&)
        WHERE (status = 'booked')
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_audit_log_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only' USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_append_only
        BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_log_mutation()
        """
    )


def downgrade() -> None:
    for table_name in (
        "payment",
        "invoice_item",
        "annotation",
        "cdss_result",
        "invoice",
        "scan",
        "rehab_session",
        "prescription",
        "treatment_plan",
        "medical_record",
        "appointment",
        "staff",
        "patient",
        "audit_log",
        "service",
        "icd10_code",
        "user",
    ):
        op.drop_table(table_name)
    op.execute("DROP FUNCTION reject_audit_log_mutation()")
