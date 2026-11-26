"""Shared validation, audit, pagination, and database helpers."""

from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from functools import wraps
from typing import Any

from flask import Response, has_request_context, request
from sqlalchemy import func, insert, select
from sqlalchemy.engine import Connection, Engine

from app.api.v1.responses import list_response
from app.auth.permissions import current_actor
from app.errors import ApiError
from app.extensions import db as sqla_db
from app.models import AuditLog

MAX_ID = 2_147_483_647
MAX_MONEY = Decimal("99999999.99")
CENT = Decimal("0.01")


def db() -> Engine:
    return sqla_db.engine


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def clean_row(row: Mapping[Any, Any]) -> dict[str, Any]:
    return {
        str(key): (value.value if isinstance(value, Enum) else value)
        for key, value in row.items()
    }


def require_roles(
    *roles: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def wrap(handler: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(handler)
        def check(*args: Any, **kwargs: Any) -> Any:
            actor = current_actor()
            if actor.role.value not in roles:
                raise ApiError(
                    403, "forbidden", "Your role cannot perform this action."
                )
            return handler(*args, **kwargs)

        return check

    return wrap


def audit(target: Any, action: str, resource: str, user_id: int | None = None) -> None:
    actor_id = current_actor().user_id if user_id is None else user_id
    ip_addr = request.remote_addr if has_request_context() else None
    if isinstance(target, Connection):
        target.execute(
            insert(AuditLog).values(
                user_id=actor_id,
                action=action,
                resource=resource,
                ip_address=ip_addr,
            )
        )
    else:
        target.add(
            AuditLog(
                user_id=actor_id,
                action=action,
                resource=resource,
                ip_address=ip_addr,
            )
        )


def body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "invalid", "Provide a JSON object.")
    return data


def as_int(value: Any, name: str, *, maximum: int = MAX_ID) -> int:
    if type(value) is int:
        result = value
    elif (
        isinstance(value, str)
        and len(value) <= 10
        and value.isascii()
        and value.isdecimal()
    ):
        result = int(value)
    else:
        result = 0
    if not 1 <= result <= maximum:
        raise ApiError(422, "value", f"{name} must be an integer from 1 to {maximum}.")
    return result


def as_money(value: Any, name: str, *, positive: bool = False) -> Decimal:
    if type(value) not in (str, int, float, Decimal) or len(str(value)) > 24:
        raise ApiError(422, "value", f"{name} must be a decimal amount.")
    try:
        number = Decimal(str(value))
        if not number.is_finite() or not 0 <= number <= MAX_MONEY:
            raise InvalidOperation
        if number != number.quantize(CENT) or (positive and number == 0):
            raise InvalidOperation
    except InvalidOperation:
        raise ApiError(
            422, "value", f"{name} is outside the allowed amount or precision."
        ) from None
    return number.quantize(CENT)


def as_text(value: Any, name: str, *, maximum: int, optional: bool = False) -> Any:
    if value is None and optional:
        return None
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > maximum
        or "\x00" in value
    ):
        raise ApiError(
            422, "value", f"{name} must be text of 1 to {maximum} characters."
        )
    return value.strip()


def as_date(value: Any, name: str) -> date:
    try:
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value or not 1900 <= parsed.year <= 2200:
            raise ValueError
        return parsed
    except ValueError:
        raise ApiError(
            422, "value", f"{name} must be a date in YYYY-MM-DD format."
        ) from None


def list_rows(session: Any, statement: Any, order: Any) -> Response:
    page = as_int(request.args.get("page", "1"), "page", maximum=1_000_000)
    size = as_int(request.args.get("page_size", "25"), "page_size", maximum=100)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = session.execute(
        statement.order_by(order).offset((page - 1) * size).limit(size)
    ).mappings()
    items = [clean_row(item) for item in rows]
    return list_response(items, total=int(total), page=page, page_size=size)
