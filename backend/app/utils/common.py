from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps
from typing import Any

from flask import current_app, g, has_request_context, request
from sqlalchemy import func, select

from app.models.schema_v1 import audit_log

MAX_ID = 2_147_483_647
MAX_MONEY = Decimal("99999999.99")
CENT = Decimal("0.01")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def db() -> Any:
    return current_app.extensions["ortho_db"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def require_roles(
    *roles: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def wrap(handler: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(handler)
        def check(*args: Any, **kwargs: Any) -> Any:
            if g.actor["role"] not in roles:
                raise ApiError(
                    403, "forbidden", "Your role cannot perform this action."
                )
            return handler(*args, **kwargs)

        return check

    return wrap


def audit(
    connection: Any, action: str, resource: str, user_id: int | None = None
) -> None:
    connection.execute(
        audit_log.insert().values(
            user_id=g.actor["user_id"] if user_id is None else user_id,
            action=action,
            resource=resource,
            ip_address=request.remote_addr if has_request_context() else None,
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


def page_rows(connection: Any, statement: Any, order: Any) -> dict[str, Any]:
    page = as_int(request.args.get("page", "1"), "page", maximum=1_000_000)
    size = as_int(request.args.get("page_size", "25"), "page_size", maximum=100)
    total = connection.scalar(select(func.count()).select_from(statement.subquery()))
    items = connection.execute(
        statement.order_by(order).offset((page - 1) * size).limit(size)
    ).mappings()
    return {
        "items": [dict(item) for item in items],
        "page": page,
        "page_size": size,
        "total": total,
    }
