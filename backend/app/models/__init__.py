"""Declarative ORM models for the 17-table Phase 1 schema."""

from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.billing import (
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Service,
)
from app.models.icd10_code import Icd10Code
from app.models.imaging import (
    Annotation,
    AnnotationType,
    CdssResult,
    ReviewStatus,
    Scan,
)
from app.models.medical_record import MedicalRecord
from app.models.patient import Gender, Patient
from app.models.prescription import Prescription
from app.models.rehab_session import RehabSession
from app.models.staff import Staff, StaffType
from app.models.treatment_plan import TreatmentPlan, TreatmentPlanStatus
from app.models.user import User, UserRole

metadata = Base.metadata

__all__ = [
    "Annotation",
    "AnnotationType",
    "Appointment",
    "AppointmentStatus",
    "AppointmentType",
    "AuditLog",
    "Base",
    "CdssResult",
    "Gender",
    "Icd10Code",
    "Invoice",
    "InvoiceItem",
    "InvoiceStatus",
    "MedicalRecord",
    "Patient",
    "Payment",
    "PaymentMethod",
    "PaymentStatus",
    "Prescription",
    "RehabSession",
    "ReviewStatus",
    "Scan",
    "Service",
    "Staff",
    "StaffType",
    "TreatmentPlan",
    "TreatmentPlanStatus",
    "User",
    "UserRole",
    "metadata",
]
