"""Patient profile model for F01, F02, F04 and F05."""

from datetime import date
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.billing import Invoice
    from app.models.imaging import Scan
    from app.models.medical_record import MedicalRecord
    from app.models.treatment_plan import TreatmentPlan
    from app.models.user import User


class Gender(str, Enum):
    """Values of the ``patient_gender_values`` check constraint."""

    male = "male"
    female = "female"
    other = "other"
    unknown = "unknown"


class Patient(Base):
    """A patient profile linked one-to-one to an account."""

    __tablename__ = "patient"

    patient_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.user_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[Gender] = mapped_column(
        SqlEnum(
            Gender,
            name="patient_gender_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    national_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(150), nullable=True)

    user: Mapped["User"] = relationship(
        back_populates="patient_profile", foreign_keys=[user_id]
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="patient", foreign_keys="Appointment.patient_id"
    )
    medical_records: Mapped[list["MedicalRecord"]] = relationship(
        back_populates="patient", foreign_keys="MedicalRecord.patient_id"
    )
    treatment_plans: Mapped[list["TreatmentPlan"]] = relationship(
        back_populates="patient", foreign_keys="TreatmentPlan.patient_id"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="patient", foreign_keys="Invoice.patient_id"
    )
    scans: Mapped[list["Scan"]] = relationship(
        back_populates="patient", foreign_keys="Scan.patient_id"
    )

    def __repr__(self) -> str:
        return (
            f"<Patient(patient_id={self.patient_id!r}, full_name={self.full_name!r})>"
        )
