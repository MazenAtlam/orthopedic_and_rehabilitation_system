"""F11 reporting and analytics endpoints (ORM)."""

from collections.abc import Iterator
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from flask import Blueprint, request
from sqlalchemy import Date, cast, func, select

from app.api.v1.billing import with_balances
from app.auth import load_actor
from app.extensions import db as sqla_db
from app.models import (
    Appointment,
    AuditLog,
    Icd10Code,
    Invoice,
    InvoiceStatus,
    MedicalRecord,
    Payment,
    PaymentStatus,
)
from app.utils.common import ApiError, as_date, require_roles, utcnow

reporting = Blueprint("reporting", __name__, url_prefix="/api/v1/reports")
reporting.before_request(load_actor)


def period() -> tuple[date, date]:
    end = (
        as_date(request.args["end"], "end")
        if "end" in request.args
        else utcnow().date()
    )
    start = (
        as_date(request.args["start"], "start")
        if "start" in request.args
        else end - timedelta(days=29)
    )
    if not 0 <= (end - start).days <= 365:
        raise ApiError(422, "value", "Select a date range of up to 366 days.")
    return start, end


def timestamp_range(start: date, end: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start, time.min, timezone.utc),
        datetime.combine(end + timedelta(days=1), time.min, timezone.utc),
    )


def daily(
    session: Any, column: Any, conditions: Any, *, value: Any = None
) -> dict[Any, Any]:
    day = cast(column, Date).label("date")
    aggregate = func.count() if value is None else func.sum(value)
    statement = select(day, aggregate).where(*conditions).group_by(day)
    return dict(session.execute(statement).tuples().all())


def dates(start: date, end: date) -> Iterator[date]:
    return (start + timedelta(days=offset) for offset in range((end - start).days + 1))


@reporting.get("/system")
@require_roles("admin")
def system_report() -> dict[str, Any]:
    start, end = period()
    lower, upper = timestamp_range(start, end)
    window = (Appointment.start_time >= lower, Appointment.start_time < upper)
    session = sqla_db.session
    appointments = daily(session, Appointment.start_time, window)
    logins = daily(
        session,
        AuditLog.created_at,
        (
            AuditLog.created_at >= lower,
            AuditLog.created_at < upper,
            AuditLog.action == "login",
        ),
    )
    raw_statuses = session.execute(
        select(Appointment.status, func.count())
        .where(*window)
        .group_by(Appointment.status)
    ).all()
    statuses = {
        (key.value if isinstance(key, Enum) else str(key)): int(val)
        for key, val in raw_statuses
    }
    return {
        "start": start,
        "end": end,
        "totals": {
            "appointments": sum(appointments.values()),
            "logins": sum(logins.values()),
        },
        "daily": [
            {
                "date": day,
                "appointments": appointments.get(day, 0),
                "logins": logins.get(day, 0),
            }
            for day in dates(start, end)
        ],
        "appointments_by_status": {
            status: statuses.get(status, 0)
            for status in ("booked", "completed", "cancelled", "no_show")
        },
    }


@reporting.get("/patients")
@require_roles("admin", "staff")
def patient_report() -> dict[str, Any]:
    start, end = period()
    window = MedicalRecord.visit_date.between(start, end)
    session = sqla_db.session
    patients = (
        session.scalar(
            select(func.count(MedicalRecord.patient_id.distinct())).where(window)
        )
        or 0
    )
    visits = daily(session, MedicalRecord.visit_date, [window])
    count = func.count().label("visits")
    codes = session.execute(
        select(Icd10Code.code, Icd10Code.description, count)
        .select_from(MedicalRecord)
        .join(Icd10Code, MedicalRecord.icd10_code == Icd10Code.code)
        .where(window)
        .group_by(Icd10Code.code, Icd10Code.description)
        .order_by(count.desc(), Icd10Code.code)
    ).mappings()
    diagnoses = [dict(row) for row in codes]
    return {
        "start": start,
        "end": end,
        "totals": {"patients": patients, "visits": sum(visits.values())},
        "daily": [
            {"date": day, "visits": visits.get(day, 0)} for day in dates(start, end)
        ],
        "diagnoses": diagnoses,
    }


@reporting.get("/financial")
@require_roles("admin")
def financial_report() -> dict[str, Any]:
    start, end = period()
    lower, upper = timestamp_range(start, end)
    balances = (
        with_balances()
        .where(
            Invoice.issue_date.between(start, end),
            Invoice.status != InvoiceStatus.cancelled,
        )
        .subquery()
    )
    session = sqla_db.session
    revenue = daily(
        session,
        Payment.paid_at,
        (
            Payment.paid_at >= lower,
            Payment.paid_at < upper,
            Payment.status == PaymentStatus.success,
        ),
        value=Payment.amount,
    )
    outstanding = (
        session.execute(
            select(
                func.count().label("count"),
                func.sum(balances.c.balance).label("amount"),
            ).where(balances.c.balance > 0)
        )
        .mappings()
        .one()
    )
    zero = Decimal("0.00")
    return {
        "start": start,
        "end": end,
        "currency": "EGP",
        "totals": {
            "revenue": sum(revenue.values(), zero),
            "outstanding": outstanding["amount"] or zero,
            "open_invoices": outstanding["count"],
        },
        "daily": [
            {"date": day, "revenue": revenue.get(day, zero)}
            for day in dates(start, end)
        ],
    }
