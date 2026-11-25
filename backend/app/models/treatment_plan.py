"""Rehabilitation treatment plan model for F08."""

from datetime import date
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    Text,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.rehab_session import RehabSession
    from app.models.staff import Staff


class TreatmentPlanStatus(str, Enum):
    """Values of the ``treatment_plan_status_values`` check constraint."""

    active = "active"
    completed = "completed"
    stopped = "stopped"


class TreatmentPlan(Base):
    """A rehabilitation plan owned by a patient and a clinician."""

    __tablename__ = "treatment_plan"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="plan_dates_in_order"),
    )

    plan_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
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
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[TreatmentPlanStatus] = mapped_column(
        SqlEnum(
            TreatmentPlanStatus,
            name="treatment_plan_status_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        server_default="active",
    )

    patient: Mapped["Patient"] = relationship(
        back_populates="treatment_plans", foreign_keys=[patient_id]
    )
    staff: Mapped["Staff"] = relationship(
        back_populates="treatment_plans", foreign_keys=[staff_id]
    )
    sessions: Mapped[list["RehabSession"]] = relationship(
        back_populates="plan", foreign_keys="RehabSession.plan_id"
    )

    def __repr__(self) -> str:
        return f"<TreatmentPlan(plan_id={self.plan_id!r}, title={self.title!r})>"
