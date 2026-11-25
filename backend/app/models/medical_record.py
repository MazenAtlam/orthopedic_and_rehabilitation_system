"""Musculoskeletal encounter model for F06."""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.icd10_code import Icd10Code
    from app.models.imaging import Scan
    from app.models.patient import Patient
    from app.models.prescription import Prescription
    from app.models.staff import Staff


class MedicalRecord(Base):
    """A visit record with a mandatory ICD-10 diagnosis code."""

    __tablename__ = "medical_record"
    __table_args__ = (
        UniqueConstraint("record_id", "patient_id", name="record_id_patient_key"),
    )

    record_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
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
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    chief_complaint: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    icd10_code: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("icd10_code.code", ondelete="RESTRICT"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(
        back_populates="medical_records", foreign_keys=[patient_id]
    )
    staff: Mapped["Staff"] = relationship(
        back_populates="medical_records", foreign_keys=[staff_id]
    )
    icd10: Mapped["Icd10Code"] = relationship(
        back_populates="medical_records", foreign_keys=[icd10_code]
    )
    prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="record", foreign_keys="Prescription.record_id"
    )
    scans: Mapped[list["Scan"]] = relationship(
        back_populates="record", foreign_keys="Scan.record_id"
    )

    def __repr__(self) -> str:
        return (
            f"<MedicalRecord(record_id={self.record_id!r}, "
            f"visit_date={self.visit_date!r})>"
        )
