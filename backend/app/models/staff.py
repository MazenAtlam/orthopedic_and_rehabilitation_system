"""Clinical staff model for F02, F03, F05, F06, F07 and F08."""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SqlEnum, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.medical_record import MedicalRecord
    from app.models.treatment_plan import TreatmentPlan
    from app.models.user import User


class StaffType(str, Enum):
    """Values of the ``staff_staff_type_values`` check constraint."""

    doctor = "doctor"
    physiotherapist = "physiotherapist"
    radiologist = "radiologist"
    nurse = "nurse"


class Staff(Base):
    """A clinical staff profile linked one-to-one to an account."""

    __tablename__ = "staff"

    staff_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.user_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    staff_type: Mapped[StaffType] = mapped_column(
        SqlEnum(
            StaffType,
            name="staff_staff_type_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    specialty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    license_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    user: Mapped["User"] = relationship(
        back_populates="staff_profile", foreign_keys=[user_id]
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="staff", foreign_keys="Appointment.staff_id"
    )
    medical_records: Mapped[list["MedicalRecord"]] = relationship(
        back_populates="staff", foreign_keys="MedicalRecord.staff_id"
    )
    treatment_plans: Mapped[list["TreatmentPlan"]] = relationship(
        back_populates="staff", foreign_keys="TreatmentPlan.staff_id"
    )

    def __repr__(self) -> str:
        return f"<Staff(staff_id={self.staff_id!r}, staff_type={self.staff_type!r})>"
