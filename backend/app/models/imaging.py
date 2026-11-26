"""Imaging, CDSS and annotation models (Phase 1 Table 3 singular table names)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.medical_record import MedicalRecord
    from app.models.patient import Patient


class AnnotationType(str, Enum):
    """Values of the ``annotation_type_values`` check constraint."""

    arrow = "arrow"
    length = "length"
    angle = "angle"
    note = "note"


class ReviewStatus(str, Enum):
    """Values of the ``cdss_result_review_status_values`` check constraint."""

    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class Scan(Base):
    """An uploaded imaging study metadata record (table ``scan``)."""

    __tablename__ = "scan"
    __table_args__ = (
        ForeignKeyConstraint(
            ["record_id", "patient_id"],
            ["medical_record.record_id", "medical_record.patient_id"],
            name="scan_record_patient_fk",
            ondelete="RESTRICT",
        ),
    )

    scan_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patient.patient_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    record_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("medical_record.record_id", ondelete="RESTRICT"),
        nullable=True,
    )
    study_uid: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    orthanc_id: Mapped[str] = mapped_column(String(64), nullable=False)
    modality: Mapped[str | None] = mapped_column(String(10), nullable=True)
    body_part: Mapped[str | None] = mapped_column(String(50), nullable=True)
    study_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("staff.staff_id", ondelete="RESTRICT"),
        nullable=False,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    patient: Mapped["Patient"] = relationship(
        back_populates="scans", foreign_keys=[patient_id]
    )
    record: Mapped["MedicalRecord | None"] = relationship(
        back_populates="scans", foreign_keys=[record_id]
    )
    cdss_results: Mapped[list["CdssResult"]] = relationship(
        back_populates="scan", foreign_keys="CdssResult.scan_id"
    )
    annotations: Mapped[list["Annotation"]] = relationship(
        back_populates="scan", foreign_keys="Annotation.scan_id"
    )

    def __repr__(self) -> str:
        return f"<Scan(scan_id={self.scan_id!r}, study_uid={self.study_uid!r})>"


class CdssResult(Base):
    """A clinical-decision-support result for one scan (table ``cdss_result``)."""

    __tablename__ = "cdss_result"
    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="cdss_confidence_0_to_1"),
        CheckConstraint(
            "(review_status = 'pending' AND reviewed_by IS NULL) OR "
            "(review_status IN ('accepted', 'rejected') AND reviewed_by IS NOT NULL)",
            name="cdss_review_has_reviewer",
        ),
    )

    result_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scan.scan_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    finding: Mapped[str | None] = mapped_column(String(150), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float(precision=24), nullable=True)
    report_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[ReviewStatus] = mapped_column(
        SqlEnum(
            ReviewStatus,
            name="cdss_result_review_status_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        server_default="pending",
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("staff.staff_id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    scan: Mapped["Scan"] = relationship(
        back_populates="cdss_results", foreign_keys=[scan_id]
    )

    def __repr__(self) -> str:
        return (
            f"<CdssResult(result_id={self.result_id!r}, "
            f"review_status={self.review_status!r})>"
        )


class Annotation(Base):
    """A measurement or note saved on an imaging study (table ``annotation``)."""

    __tablename__ = "annotation"

    annotation_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scan.scan_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("staff.staff_id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[AnnotationType] = mapped_column(
        SqlEnum(
            AnnotationType,
            name="annotation_type_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    scan: Mapped["Scan"] = relationship(
        back_populates="annotations", foreign_keys=[scan_id]
    )

    def __repr__(self) -> str:
        return f"<Annotation(annotation_id={self.annotation_id!r}, type={self.type!r})>"
