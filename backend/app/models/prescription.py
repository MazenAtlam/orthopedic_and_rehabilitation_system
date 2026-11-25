"""Prescription model for F07."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Identity, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.medical_record import MedicalRecord


class Prescription(Base):
    """Medication ordered during an F06 medical record visit."""

    __tablename__ = "prescription"

    prescription_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    record_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("medical_record.record_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    medication: Mapped[str] = mapped_column(String(150), nullable=False)
    dose: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(50), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    record: Mapped["MedicalRecord"] = relationship(
        back_populates="prescriptions", foreign_keys=[record_id]
    )

    def __repr__(self) -> str:
        return (
            f"<Prescription(prescription_id={self.prescription_id!r}, "
            f"medication={self.medication!r})>"
        )
