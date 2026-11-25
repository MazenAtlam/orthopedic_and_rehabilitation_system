"""Billing models for F09 and F10 (Phase 1 Table 3 singular table names)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.icd10_code import Icd10Code
    from app.models.patient import Patient


class InvoiceStatus(str, Enum):
    """Values of the ``invoice_status_values`` check constraint."""

    unpaid = "unpaid"
    partial = "partial"
    paid = "paid"
    cancelled = "cancelled"


class PaymentMethod(str, Enum):
    """Values of the ``payment_method_values`` check constraint."""

    cash = "cash"
    card = "card"
    online = "online"


class PaymentStatus(str, Enum):
    """Values of the ``payment_status_values`` check constraint."""

    pending = "pending"
    success = "success"
    failed = "failed"


class Service(Base):
    """A billable clinical or rehabilitation service (table ``service``)."""

    __tablename__ = "service"
    __table_args__ = (CheckConstraint("price >= 0", name="service_price_nonnegative"),)

    service_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    invoice_items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="service", foreign_keys="InvoiceItem.service_id"
    )

    def __repr__(self) -> str:
        return f"<Service(service_id={self.service_id!r}, name={self.name!r})>"


class Invoice(Base):
    """A patient invoice containing priced service lines (table ``invoice``)."""

    __tablename__ = "invoice"
    __table_args__ = (
        CheckConstraint("due_date >= issue_date", name="invoice_dates_in_order"),
        CheckConstraint("total_amount >= 0", name="invoice_total_nonnegative"),
    )

    invoice_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patient.patient_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("appointment.appointment_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    icd10_code: Mapped[str | None] = mapped_column(
        String(10),
        ForeignKey("icd10_code.code", ondelete="RESTRICT"),
        nullable=True,
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        SqlEnum(
            InvoiceStatus,
            name="invoice_status_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        server_default="unpaid",
    )

    patient: Mapped["Patient"] = relationship(
        back_populates="invoices", foreign_keys=[patient_id]
    )
    appointment: Mapped["Appointment | None"] = relationship(
        back_populates="invoices", foreign_keys=[appointment_id]
    )
    icd10: Mapped["Icd10Code | None"] = relationship(foreign_keys=[icd10_code])
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", foreign_keys="InvoiceItem.invoice_id"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="invoice", foreign_keys="Payment.invoice_id"
    )

    def __repr__(self) -> str:
        return f"<Invoice(invoice_id={self.invoice_id!r}, status={self.status!r})>"


class InvoiceItem(Base):
    """One service line on an invoice (table ``invoice_item``)."""

    __tablename__ = "invoice_item"
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="invoice_item_positive_quantity"),
        CheckConstraint("unit_price >= 0", name="invoice_item_price_nonnegative"),
    )

    item_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("invoice.invoice_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("service.service_id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    invoice: Mapped["Invoice"] = relationship(
        back_populates="items", foreign_keys=[invoice_id]
    )
    service: Mapped["Service"] = relationship(
        back_populates="invoice_items", foreign_keys=[service_id]
    )

    def __repr__(self) -> str:
        return (
            f"<InvoiceItem(item_id={self.item_id!r}, service_id={self.service_id!r})>"
        )


class Payment(Base):
    """A payment applied to an invoice (table ``payment``)."""

    __tablename__ = "payment"
    __table_args__ = (
        UniqueConstraint(
            "invoice_id", "idempotency_key", name="payment_invoice_request_once"
        ),
        CheckConstraint("amount > 0", name="payment_amount_positive"),
        CheckConstraint(
            "status <> 'success' OR paid_at IS NOT NULL", name="payment_success_date"
        ),
    )

    payment_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("invoice.invoice_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        SqlEnum(
            PaymentMethod,
            name="payment_method_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SqlEnum(
            PaymentStatus,
            name="payment_status_values",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    invoice: Mapped["Invoice"] = relationship(
        back_populates="payments", foreign_keys=[invoice_id]
    )

    def __repr__(self) -> str:
        return f"<Payment(payment_id={self.payment_id!r}, amount={self.amount!r})>"
