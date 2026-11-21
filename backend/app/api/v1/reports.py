from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from flask import Blueprint, request
from sqlalchemy import Date, cast, func, select

from app.utils.access import load_actor
from app.api.v1.billing import with_balances
from app.utils.common import ApiError, as_date, db, require_roles, utcnow
from app.models.schema_v1 import appointment, audit_log, icd10_code, invoice, medical_record, payment

reporting = Blueprint("reporting", __name__, url_prefix="/api/v1/reports")
reporting.before_request(load_actor)


def period():
    end = as_date(request.args["end"], "end") if "end" in request.args else utcnow().date()
    start = as_date(request.args["start"], "start") if "start" in request.args else end - timedelta(days=29)
    if not 0 <= (end - start).days <= 365:
        raise ApiError(422, "value", "Select a date range of up to 366 days.")
    return start, end


def timestamp_range(start, end):
    return (
        datetime.combine(start, time.min, timezone.utc),
        datetime.combine(end + timedelta(days=1), time.min, timezone.utc),
    )


def daily(connection, column, conditions, *, value=None):
    day = cast(column, Date).label("date")
    aggregate = func.count() if value is None else func.sum(value)
    statement = select(day, aggregate).where(*conditions).group_by(day)
    return dict(connection.execute(statement).all())


def dates(start, end):
    return (start + timedelta(days=offset) for offset in range((end - start).days + 1))


@reporting.get("/system")
@require_roles("admin")
def system_report():
    start, end = period()
    lower, upper = timestamp_range(start, end)
    window = (appointment.c.start_time >= lower, appointment.c.start_time < upper)
    with db().connect() as connection:
        appointments = daily(connection, appointment.c.start_time, window)
        logins = daily(connection, audit_log.c.created_at, (
            audit_log.c.created_at >= lower, audit_log.c.created_at < upper, audit_log.c.action == "login",
        ))
        statuses = dict(connection.execute(
            select(appointment.c.status, func.count()).where(*window).group_by(appointment.c.status)
        ).all())
    return {
        "start": start, "end": end,
        "totals": {"appointments": sum(appointments.values()), "logins": sum(logins.values())},
        "daily": [{"date": day, "appointments": appointments.get(day, 0), "logins": logins.get(day, 0)}
                  for day in dates(start, end)],
        "appointments_by_status": {status: statuses.get(status, 0) for status in (
            "booked", "completed", "cancelled", "no_show"
        )},
    }


@reporting.get("/patients")
@require_roles("admin", "staff")
def patient_report():
    start, end = period()
    window = medical_record.c.visit_date.between(start, end)
    with db().connect() as connection:
        patients = connection.scalar(select(func.count(
            medical_record.c.patient_id.distinct()
        )).where(window))
        visits = daily(connection, medical_record.c.visit_date, [window])
        count = func.count().label("visits")
        codes = connection.execute(select(
            icd10_code.c.code, icd10_code.c.description, count
        ).select_from(medical_record.join(icd10_code)).where(window).group_by(
            icd10_code.c.code, icd10_code.c.description
        ).order_by(count.desc(), icd10_code.c.code)).mappings()
        diagnoses = [dict(row) for row in codes]
    return {
        "start": start, "end": end, "totals": {"patients": patients, "visits": sum(visits.values())},
        "daily": [{"date": day, "visits": visits.get(day, 0)} for day in dates(start, end)],
        "diagnoses": diagnoses,
    }


@reporting.get("/financial")
@require_roles("admin")
def financial_report():
    start, end = period()
    lower, upper = timestamp_range(start, end)
    balances = with_balances().where(
        invoice.c.issue_date.between(start, end), invoice.c.status != "cancelled"
    ).subquery()
    with db().connect() as connection:
        revenue = daily(connection, payment.c.paid_at, (
            payment.c.paid_at >= lower, payment.c.paid_at < upper, payment.c.status == "success",
        ), value=payment.c.amount)
        outstanding = connection.execute(select(
            func.count().label("count"), func.sum(balances.c.balance).label("amount"),
        ).where(balances.c.balance > 0)).mappings().one()
    zero = Decimal("0.00")
    return {
        "start": start, "end": end, "currency": "EGP",
        "totals": {"revenue": sum(revenue.values(), zero), "outstanding": outstanding["amount"] or zero,
                   "open_invoices": outstanding["count"]},
        "daily": [{"date": day, "revenue": revenue.get(day, zero)} for day in dates(start, end)],
    }
