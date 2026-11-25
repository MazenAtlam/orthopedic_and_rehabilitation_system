"""Account model for F01, F02 and F03."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SqlEnum,
    Identity,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.patient import Patient
    from app.models.staff import Staff


class UserRole(str, Enum):
    """Values of the ``user_role_values`` check constraint."""

    admin = "admin"
    staff = "staff"
    patient = "patient"


class User(Base):
    """A login account. Accounts are deactivated rather than deleted."""

    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            name="user_role_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    patient_profile: Mapped["Patient | None"] = relationship(
        back_populates="user", uselist=False, foreign_keys="Patient.user_id"
    )
    staff_profile: Mapped["Staff | None"] = relationship(
        back_populates="user", uselist=False, foreign_keys="Staff.user_id"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="user", foreign_keys="AuditLog.user_id"
    )

    def __repr__(self) -> str:
        return f"<User(user_id={self.user_id!r}, email={self.email!r})>"
