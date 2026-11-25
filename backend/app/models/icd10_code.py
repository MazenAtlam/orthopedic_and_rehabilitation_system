"""ICD-10 reference data used by F06 and B1."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.medical_record import MedicalRecord


class Icd10Code(Base):
    """A reference ICD-10 code; the primary key is the code itself."""

    __tablename__ = "icd10_code"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    medical_records: Mapped[list["MedicalRecord"]] = relationship(
        back_populates="icd10", foreign_keys="MedicalRecord.icd10_code"
    )

    def __repr__(self) -> str:
        return f"<Icd10Code(code={self.code!r}, description={self.description!r})>"
