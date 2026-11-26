"""F09 billing, F10 simulated payments, and B1 ICD-10 lookup (ORM)."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any
import uuid

from flask import Blueprint, Response, current_app, request
from sqlalchemy import func, or_, select

from app.auth import current_actor, load_actor
from app.extensions import db as sqla_db
from app.models import (
    Appointment,
    Icd10Code,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    Patient,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Service,
)
from app.utils.common import (
    MAX_ID,
    MAX_MONEY,
    ApiError,
    as_date,
    as_int,
    as_money,
    as_text,
    audit,
    body,
    clean_row,
    list_rows,
    require_roles,
    utcnow,
)

billing = Blueprint("billing", __name__, url_prefix="/api/v1")
billing.before_request(load_actor)


def filter_like(value: str) -> str:
    return (
        "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    )


def _serialize_service(item: Service) -> dict[str, Any]:
    return {
        "service_id": item.service_id,
        "name": item.name,
        "description": item.description,
        "price": item.price,
        "is_active": item.is_active,
    }


@billing.get("/services")
def services_list() -> Response:
    actor = current_actor()
    statement = select(Service.__table__)
    if not actor.is_admin or request.args.get("include_inactive") != "true":
        statement = statement.where(Service.is_active.is_(True))
    return list_rows(sqla_db.session, statement, Service.service_id)


@billing.post("/services")
@require_roles("admin")
def service_save() -> tuple[dict[str, Any], int]:
    data = body()
    active = data.get("is_active", True)
    if type(active) is not bool:
        raise ApiError(422, "value", "is_active must be a boolean.")
    name = as_text(data.get("name"), "name", maximum=150)
    description = as_text(
        data.get("description"), "description", maximum=4000, optional=True
    )
    price = as_money(data.get("price"), "price")

    item_id = data.get("service_id")
    if item_id is None:
        record = Service(
            name=name, description=description, price=price, is_active=active
        )
        sqla_db.session.add(record)
        sqla_db.session.flush()
        audit(sqla_db.session, "create", f"service/{record.service_id}")
        sqla_db.session.commit()
        return _serialize_service(record), 201

    parsed_id = as_int(item_id, "service_id")
    existing = sqla_db.session.get(Service, parsed_id)
    if existing is None:
        raise ApiError(404, "not-found", "Service not found.")
    existing.name = name
    existing.description = description
    existing.price = price
    existing.is_active = active
    sqla_db.session.flush()
    audit(sqla_db.session, "update", f"service/{existing.service_id}")
    sqla_db.session.commit()
    return _serialize_service(existing), 200


@billing.get("/icd10")
@require_roles("admin", "staff")
def icd10_lookup() -> Response:
    query = (request.args.get("q") or request.args.get("search") or "").strip()
    if len(query) > 100:
        raise ApiError(422, "value", "q can have up to 100 characters.")
    statement = select(Icd10Code.__table__)
    if query:
        pattern = filter_like(query)
        statement = statement.where(
            or_(
                Icd10Code.code.ilike(pattern, escape="\\"),
                Icd10Code.description.ilike(pattern, escape="\\"),
                Icd10Code.category.ilike(pattern, escape="\\"),
            )
        )
    return list_rows(sqla_db.session, statement, Icd10Code.code)


def payment_totals() -> Any:
    return (
        select(Payment.invoice_id, func.sum(Payment.amount).label("paid"))
        .where(Payment.status == PaymentStatus.success)
        .group_by(Payment.invoice_id)
        .subquery()
    )


def with_balances() -> Any:
    totals = payment_totals()
    paid = func.coalesce(totals.c.paid, Decimal("0.00"))
    return select(
        Invoice.__table__,
        paid.label("amount_paid"),
        (Invoice.total_amount - paid).label("balance"),
    ).select_from(
        Invoice.__table__.outerjoin(totals, Invoice.invoice_id == totals.c.invoice_id)
    )


def visible(statement: Any) -> Any:
    actor = current_actor()
    if actor.is_patient:
        return statement.where(Invoice.patient_id == actor.patient_id)
    return statement


def invoice_details(session: Any, invoice_id: int) -> dict[str, Any]:
    row = (
        session.execute(
            visible(with_balances()).where(Invoice.invoice_id == invoice_id)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "not-found", "Invoice not found.")

    items = session.execute(
        select(
            InvoiceItem.item_id,
            InvoiceItem.service_id,
            Service.name.label("service_name"),
            InvoiceItem.quantity,
            InvoiceItem.unit_price,
            (InvoiceItem.quantity * InvoiceItem.unit_price).label("line_total"),
        )
        .select_from(InvoiceItem)
        .join(Service, InvoiceItem.service_id == Service.service_id)
        .where(InvoiceItem.invoice_id == invoice_id)
        .order_by(InvoiceItem.item_id)
    ).mappings()
    payments = session.execute(
        select(
            Payment.payment_id,
            Payment.amount,
            Payment.method,
            Payment.status,
            Payment.paid_at,
        )
        .where(Payment.invoice_id == invoice_id)
        .order_by(Payment.payment_id)
    ).mappings()
    return {
        **clean_row(row),
        "items": [clean_row(item) for item in items],
        "payments": [clean_row(item) for item in payments],
    }


@billing.get("/invoices")
def invoice_list() -> Response:
    statement = visible(with_balances())
    if "patient_id" in request.args:
        statement = statement.where(
            Invoice.patient_id == as_int(request.args["patient_id"], "patient_id")
        )
    if "status" in request.args:
        status = request.args["status"]
        if status not in ("unpaid", "partial", "paid", "cancelled"):
            raise ApiError(422, "value", "Unknown invoice status.")
        statement = statement.where(Invoice.status == InvoiceStatus(status))
    return list_rows(sqla_db.session, statement, Invoice.invoice_id.desc())


@billing.get("/invoices/<int:invoice_id>")
def invoice_read(invoice_id: int) -> dict[str, Any]:
    invoice_id = as_int(invoice_id, "invoice_id")
    return invoice_details(sqla_db.session, invoice_id)


def calculate_invoice_total(
    prices: Mapping[int, Decimal], quantities: Mapping[int, int]
) -> Decimal:
    if not quantities:
        raise ApiError(422, "value", "Provide at least one invoice item.")
    total = sum(
        (prices[key] * quantity for key, quantity in quantities.items()),
        Decimal("0.00"),
    )
    if total > MAX_MONEY:
        raise ApiError(
            422, "value", "Invoice total exceeds the maximum allowed amount."
        )
    return total


@billing.post("/invoices")
@require_roles("admin", "staff")
def invoice_create() -> tuple[dict[str, Any], int]:
    data = body()
    patient_id = as_int(data.get("patient_id"), "patient_id")
    appointment_id = data.get("appointment_id")
    if appointment_id is not None:
        appointment_id = as_int(appointment_id, "appointment_id")
    diagnosis = as_text(data.get("icd10_code"), "icd10_code", maximum=10, optional=True)
    issue = (
        as_date(data["issue_date"], "issue_date")
        if "issue_date" in data
        else utcnow().date()
    )
    due = as_date(data.get("due_date"), "due_date")
    if due < issue:
        raise ApiError(422, "value", "The due date must be on or after the issue date.")
    items = data.get("items")
    if (
        not isinstance(items, list)
        or not 1 <= len(items) <= 100
        or any(not isinstance(i, dict) for i in items)
    ):
        raise ApiError(422, "value", "Provide between 1 and 100 invoice items.")
    quantities: dict[int, int] = {}
    for item in items:
        service_id = as_int(item.get("service_id"), "service_id")
        if service_id in quantities:
            raise ApiError(
                422, "duplicate", "Include each service once and set its quantity."
            )
        quantities[service_id] = as_int(
            item.get("quantity"), "quantity", maximum=10_000
        )

    session = sqla_db.session
    if not session.scalar(
        select(Patient.patient_id).where(Patient.patient_id == patient_id)
    ):
        raise ApiError(404, "not-found", "Patient not found.")
    if appointment_id is not None:
        owner = session.scalar(
            select(Appointment.patient_id).where(
                Appointment.appointment_id == appointment_id
            )
        )
        if owner != patient_id:
            raise ApiError(
                422, "value", "The appointment must belong to the invoice patient."
            )
    if diagnosis and not session.scalar(
        select(Icd10Code.code).where(Icd10Code.code == diagnosis)
    ):
        raise ApiError(422, "code-invalid", "Choose an ICD-10 code from the catalogue.")

    prices: dict[int, Decimal] = dict(
        session.execute(
            select(Service.service_id, Service.price).where(
                Service.service_id.in_(quantities), Service.is_active.is_(True)
            )
        )
        .tuples()
        .all()
    )
    if len(prices) != len(quantities):
        raise ApiError(
            422, "value", "Each invoice item must refer to an active service."
        )
    total = calculate_invoice_total(prices, quantities)
    bill = Invoice(
        patient_id=patient_id,
        appointment_id=appointment_id,
        icd10_code=diagnosis,
        issue_date=issue,
        due_date=due,
        total_amount=total,
        status=InvoiceStatus.unpaid if total else InvoiceStatus.paid,
    )
    session.add(bill)
    session.flush()
    for key, quantity in quantities.items():
        session.add(
            InvoiceItem(
                invoice_id=bill.invoice_id,
                service_id=key,
                quantity=quantity,
                unit_price=prices[key],
            )
        )
    session.flush()
    audit(session, "create", f"invoice/{bill.invoice_id}")
    details = invoice_details(session, bill.invoice_id)
    session.commit()
    return details, 201


@billing.post("/invoices/<int:invoice_id>/payments")
@require_roles("admin", "patient")
def pay(invoice_id: int) -> tuple[dict[str, Any], int]:
    invoice_id = as_int(invoice_id, "invoice_id", maximum=MAX_ID)
    data = body()
    amount = as_money(data.get("amount"), "amount", positive=True)
    method = data.get("method", "online")
    if method not in ("online", "cash", "card"):
        raise ApiError(422, "value", "Choose online, cash or card.")
    actor = current_actor()
    if actor.is_patient and method != "online":
        raise ApiError(403, "forbidden", "Patients can use simulated online payment.")
    raw_key = request.headers.get("Idempotency-Key")
    key = (
        as_text(raw_key, "Idempotency-Key", maximum=128)
        if raw_key is not None
        else uuid.uuid4().hex
    )
    result = data.get("simulate", "success")
    if result != "success" and not (
        result == "declined"
        and method == "online"
        and current_app.config.get("DEMO_MODE")
    ):
        raise ApiError(422, "value", "Choose an available payment simulation result.")
    status = PaymentStatus.success if result == "success" else PaymentStatus.failed

    session = sqla_db.session
    locked = (
        visible(select(Invoice))
        .where(Invoice.invoice_id == invoice_id)
        .with_for_update()
    )
    bill = session.scalars(locked).one_or_none()
    if bill is None:
        raise ApiError(404, "not-found", "Invoice not found.")
    prior = session.scalars(
        select(Payment).where(
            Payment.invoice_id == invoice_id, Payment.idempotency_key == key
        )
    ).one_or_none()
    if prior is not None:
        if (prior.amount, prior.method.value, prior.status) != (amount, method, status):
            raise ApiError(
                409,
                "conflict",
                "This payment request key already has different details.",
            )
        return payment_response(session, prior), 200

    paid = session.scalar(
        select(func.sum(Payment.amount)).where(
            Payment.invoice_id == invoice_id, Payment.status == PaymentStatus.success
        )
    ) or Decimal("0.00")
    remaining = bill.total_amount - paid
    if (
        bill.status in (InvoiceStatus.cancelled, InvoiceStatus.paid)
        or amount > remaining
    ):
        raise ApiError(
            409, "conflict", "The amount exceeds the payable invoice balance."
        )
    saved = Payment(
        invoice_id=invoice_id,
        amount=amount,
        method=PaymentMethod(method),
        status=status,
        paid_at=utcnow() if status is PaymentStatus.success else None,
        idempotency_key=key,
    )
    session.add(saved)
    session.flush()
    if status is PaymentStatus.success:
        bill.status = (
            InvoiceStatus.paid if amount == remaining else InvoiceStatus.partial
        )
        session.flush()
    audit(
        session,
        "payment_success" if status is PaymentStatus.success else "payment_failed",
        f"payment/{saved.payment_id}",
    )
    payload = payment_response(session, saved)
    session.commit()
    return payload, 201


def payment_response(session: Any, row: Payment) -> dict[str, Any]:
    return {
        "payment": {
            "payment_id": row.payment_id,
            "invoice_id": row.invoice_id,
            "amount": row.amount,
            "method": row.method.value,
            "status": row.status.value,
            "paid_at": row.paid_at,
        },
        "invoice": invoice_details(session, row.invoice_id),
    }
