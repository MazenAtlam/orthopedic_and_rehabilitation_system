"""Appointment model for F05."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    Text,
    column,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint as _ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.billing import Invoice
    from app.models.patient import Patient
    from app.models.rehab_session import RehabSession
    from app.models.staff import Staff

ExcludeConstraint: Any = _ExcludeConstraint


class AppointmentType(str, Enum):
    """Values of the ``appointment_type_values`` check constraint."""

    consultation = "consultation"
    therapy = "therapy"
    imaging = "imaging"


class AppointmentStatus(str, Enum):
    """Values of the ``appointment_status_values`` check constraint."""

    booked = "booked"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"


class Appointment(Base):
    """A booked clinical slot; cancellation is a status change, not a delete."""

    __tablename__ = "appointment"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="appointment_end_after_start"),
        ExcludeConstraint(
            (column("staff_id"), "="),
            (
                func.tstzrange(column("start_time"), column("end_time"), text("'[)'")),
                "&&",
            ),
            using="gist",
            name="appointment_staff_no_overlap",
            where=text("status = 'booked'"),
        ),
    )

    appointment_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patient.patient_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    staff_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("staff.staff_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    type: Mapped[AppointmentType] = mapped_column(
        SqlEnum(
            AppointmentType,
            name="appointment_type_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        SqlEnum(
            AppointmentStatus,
            name="appointment_status_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        server_default="booked",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(
        back_populates="appointments", foreign_keys=[patient_id]
    )
    staff: Mapped["Staff"] = relationship(
        back_populates="appointments", foreign_keys=[staff_id]
    )
    rehab_session: Mapped["RehabSession | None"] = relationship(
        back_populates="appointment",
        uselist=False,
        foreign_keys="RehabSession.appointment_id",
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="appointment", foreign_keys="Invoice.appointment_id"
    )

    def __repr__(self) -> str:
        return (
            f"<Appointment(appointment_id={self.appointment_id!r}, "
            f"status={self.status!r})>"
        )
