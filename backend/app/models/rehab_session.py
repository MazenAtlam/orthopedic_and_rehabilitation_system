"""Rehabilitation session model for F08."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    SmallInteger,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.treatment_plan import TreatmentPlan


class RehabSession(Base):
    """One rehabilitation session with pain and range-of-motion measurements."""

    __tablename__ = "rehab_session"
    __table_args__ = (
        CheckConstraint(
            "pain_score BETWEEN 0 AND 10", name="rehab_session_pain_0_to_10"
        ),
        CheckConstraint(
            "range_of_motion >= 0", name="rehab_session_motion_nonnegative"
        ),
    )

    session_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("treatment_plan.plan_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("appointment.appointment_id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    exercises: Mapped[str | None] = mapped_column(Text, nullable=True)
    pain_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    range_of_motion: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped["TreatmentPlan"] = relationship(
        back_populates="sessions", foreign_keys=[plan_id]
    )
    appointment: Mapped["Appointment | None"] = relationship(
        back_populates="rehab_session", foreign_keys=[appointment_id]
    )

    def __repr__(self) -> str:
        return (
            f"<RehabSession(session_id={self.session_id!r}, "
            f"session_date={self.session_date!r})>"
        )
