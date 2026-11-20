from decimal import Decimal

from flask import Blueprint, current_app, g, request
from sqlalchemy import func, or_, select

from ortho.access import load_actor
from ortho.common import (
    MAX_ID, MAX_MONEY, ApiError, as_date, as_int, as_money, as_text,
    audit, body, db, page_rows, require_roles, utcnow,
)
from ortho.schema_v1 import appointment, icd10_code, invoice, invoice_item, patient, payment, service

billing = Blueprint("billing", __name__, url_prefix="/api/v1")
billing.before_request(load_actor)


def filter_like(value):
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@billing.get("/services")
def services_list():
    statement = select(service)
    if g.actor["role"] != "admin" or request.args.get("include_inactive") != "true":
        statement = statement.where(service.c.is_active.is_(True))
    with db().connect() as connection:
        return page_rows(connection, statement, service.c.service_id)


@billing.post("/services")
@require_roles("admin")
def service_save():
    data = body()
    active = data.get("is_active", True)
    if type(active) is not bool:
        raise ApiError(422, "value", "is_active must be a boolean.")
    values = {
        "name": as_text(data.get("name"), "name", maximum=150),
        "description": as_text(data.get("description"), "description", maximum=4000, optional=True),
        "price": as_money(data.get("price"), "price"),
        "is_active": active,
    }
    with db().begin() as connection:
        item_id = data.get("service_id")
        if item_id is None:
            statement = service.insert()
        else:
            item_id = as_int(item_id, "service_id")
            statement = service.update().where(service.c.service_id == item_id)
        result = connection.execute(statement.values(**values).returning(service)).mappings().one_or_none()
        if result is None:
            raise ApiError(404, "not-found", "Service not found.")
        audit(connection, "create" if item_id is None else "update", f"service/{result['service_id']}")
        return dict(result), 201 if item_id is None else 200


@billing.get("/icd10")
@require_roles("admin", "staff")
def icd10_lookup():
    query = request.args.get("q", "").strip()
    if len(query) > 100:
        raise ApiError(422, "value", "q can have up to 100 characters.")
    statement = select(icd10_code)
    if query:
        pattern = filter_like(query)
        statement = statement.where(or_(
            icd10_code.c.code.ilike(pattern, escape="\\"),
            icd10_code.c.description.ilike(pattern, escape="\\"),
        ))
    with db().connect() as connection:
        return page_rows(connection, statement, icd10_code.c.code)


def payment_totals():
    return (
        select(payment.c.invoice_id, func.sum(payment.c.amount).label("paid"))
        .where(payment.c.status == "success").group_by(payment.c.invoice_id).subquery()
    )


def with_balances():
    totals = payment_totals()
    paid = func.coalesce(totals.c.paid, Decimal("0.00"))
    return (
        select(invoice, paid.label("amount_paid"), (invoice.c.total_amount - paid).label("balance"))
        .select_from(invoice.outerjoin(totals, invoice.c.invoice_id == totals.c.invoice_id))
    )


def visible(statement):
    if g.actor["role"] == "patient":
        return statement.where(invoice.c.patient_id == g.actor["patient_id"])
    return statement


def invoice_details(connection, invoice_id):
    row = connection.execute(visible(with_balances()).where(
        invoice.c.invoice_id == invoice_id
    )).mappings().one_or_none()
    if row is None:
        raise ApiError(404, "not-found", "Invoice not found.")

    items = connection.execute(select(
        invoice_item.c.item_id, invoice_item.c.service_id, service.c.name.label("service_name"),
        invoice_item.c.quantity, invoice_item.c.unit_price,
        (invoice_item.c.quantity * invoice_item.c.unit_price).label("line_total"),
    ).select_from(invoice_item.join(service)).where(
        invoice_item.c.invoice_id == invoice_id
    ).order_by(invoice_item.c.item_id)).mappings()
    payments = connection.execute(select(
        payment.c.payment_id, payment.c.amount, payment.c.method, payment.c.status, payment.c.paid_at
    ).where(payment.c.invoice_id == invoice_id).order_by(payment.c.payment_id)).mappings()
    return {**row, "items": [dict(item) for item in items], "payments": [dict(item) for item in payments]}


@billing.get("/invoices")
def invoice_list():
    statement = visible(with_balances())
    if "patient_id" in request.args:
        statement = statement.where(invoice.c.patient_id == as_int(request.args["patient_id"], "patient_id"))
    if "status" in request.args:
        status = request.args["status"]
        if status not in ("unpaid", "partial", "paid", "cancelled"):
            raise ApiError(422, "value", "Unknown invoice status.")
        statement = statement.where(invoice.c.status == status)
    with db().connect() as connection:
        return page_rows(connection, statement, invoice.c.invoice_id.desc())


@billing.get("/invoices/<int:invoice_id>")
def invoice_read(invoice_id):
    invoice_id = as_int(invoice_id, "invoice_id")
    with db().connect() as connection:
        return invoice_details(connection, invoice_id)


@billing.post("/invoices")
@require_roles("admin", "staff")
def invoice_create():
    data = body()
    patient_id = as_int(data.get("patient_id"), "patient_id")
    appointment_id = data.get("appointment_id")
    if appointment_id is not None:
        appointment_id = as_int(appointment_id, "appointment_id")
    diagnosis = as_text(data.get("icd10_code"), "icd10_code", maximum=10, optional=True)
    issue = as_date(data["issue_date"], "issue_date") if "issue_date" in data else utcnow().date()
    due = as_date(data.get("due_date"), "due_date")
    if due < issue:
        raise ApiError(422, "value", "The due date must be on or after the issue date.")
    items = data.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 100 or any(not isinstance(i, dict) for i in items):
        raise ApiError(422, "value", "Provide between 1 and 100 invoice items.")
    quantities = {}
    for item in items:
        service_id = as_int(item.get("service_id"), "service_id")
        if service_id in quantities:
            raise ApiError(422, "duplicate", "Include each service once and set its quantity.")
        quantities[service_id] = as_int(item.get("quantity"), "quantity", maximum=10_000)

    with db().begin() as connection:
        if not connection.scalar(select(patient.c.patient_id).where(patient.c.patient_id == patient_id)):
            raise ApiError(404, "not-found", "Patient not found.")
        if appointment_id is not None:
            owner = connection.scalar(select(appointment.c.patient_id).where(
                appointment.c.appointment_id == appointment_id
            ))
            if owner != patient_id:
                raise ApiError(422, "value", "The appointment must belong to the invoice patient.")
        if diagnosis and not connection.scalar(select(icd10_code.c.code).where(icd10_code.c.code == diagnosis)):
            raise ApiError(422, "code-invalid", "Choose an ICD-10 code from the catalogue.")

        prices = dict(connection.execute(select(service.c.service_id, service.c.price).where(
            service.c.service_id.in_(quantities), service.c.is_active.is_(True)
        )).all())
        if len(prices) != len(quantities):
            raise ApiError(422, "value", "Each invoice item must refer to an active service.")
        total = sum((prices[key] * quantity for key, quantity in quantities.items()), Decimal("0.00"))
        if total > MAX_MONEY:
            raise ApiError(422, "value", "Invoice total exceeds the maximum allowed amount.")
        invoice_id = connection.scalar(invoice.insert().values(
            patient_id=patient_id, appointment_id=appointment_id, icd10_code=diagnosis,
            issue_date=issue, due_date=due, total_amount=total, status="unpaid" if total else "paid",
        ).returning(invoice.c.invoice_id))
        connection.execute(invoice_item.insert(), [
            {"invoice_id": invoice_id, "service_id": key, "quantity": quantity, "unit_price": prices[key]}
            for key, quantity in quantities.items()
        ])
        audit(connection, "create", f"invoice/{invoice_id}")
        return invoice_details(connection, invoice_id), 201


@billing.post("/invoices/<int:invoice_id>/payments")
@require_roles("admin", "patient")
def pay(invoice_id):
    invoice_id = as_int(invoice_id, "invoice_id", maximum=MAX_ID)
    data = body()
    amount = as_money(data.get("amount"), "amount", positive=True)
    method = data.get("method", "online")
    if method not in ("online", "cash", "card"):
        raise ApiError(422, "value", "Choose online, cash or card.")
    if g.actor["role"] == "patient" and method != "online":
        raise ApiError(403, "forbidden", "Patients can use simulated online payment.")
    key = as_text(request.headers.get("Idempotency-Key"), "Idempotency-Key", maximum=128)
    result = data.get("simulate", "success")
    if result != "success" and not (
        result == "declined" and method == "online" and current_app.config["DEMO_MODE"]
    ):
        raise ApiError(422, "value", "Choose an available payment simulation result.")
    status = "success" if result == "success" else "failed"

    with db().begin() as connection:
        locked = visible(select(invoice)).where(invoice.c.invoice_id == invoice_id).with_for_update()
        bill = connection.execute(locked).mappings().one_or_none()
        if bill is None:
            raise ApiError(404, "not-found", "Invoice not found.")
        prior = connection.execute(select(payment).where(
            payment.c.invoice_id == invoice_id, payment.c.idempotency_key == key
        )).mappings().one_or_none()
        if prior is not None:
            if (prior["amount"], prior["method"], prior["status"]) != (amount, method, status):
                raise ApiError(409, "conflict", "This payment request key already has different details.")
            return payment_response(connection, prior), 200

        paid = connection.scalar(select(func.sum(payment.c.amount)).where(
            payment.c.invoice_id == invoice_id, payment.c.status == "success"
        )) or Decimal("0.00")
        remaining = bill["total_amount"] - paid
        if bill["status"] in ("cancelled", "paid") or amount > remaining:
            raise ApiError(409, "conflict", "The amount exceeds the payable invoice balance.")
        saved = connection.execute(payment.insert().values(
            invoice_id=invoice_id, amount=amount, method=method, status=status,
            paid_at=utcnow() if status == "success" else None, idempotency_key=key,
        ).returning(payment)).mappings().one()
        if status == "success":
            connection.execute(invoice.update().where(invoice.c.invoice_id == invoice_id).values(
                status="paid" if amount == remaining else "partial"
            ))
        audit(connection, "payment_success" if status == "success" else "payment_failed",
              f"payment/{saved['payment_id']}")
        return payment_response(connection, saved), 201


def payment_response(connection, row):
    fields = ("payment_id", "invoice_id", "amount", "method", "status", "paid_at")
    return {"payment": {key: row[key] for key in fields},
            "invoice": invoice_details(connection, row["invoice_id"])}
