"""Structured JSON and FHIR OperationOutcome error handling."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import simplejson
from flask import Flask, Response, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException

FieldDetail = dict[str, str]
ErrorDetails = list[FieldDetail] | dict[str, Any] | None

HTTP_ERROR_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "unprocessable_entity",
    429: "too_many_requests",
    500: "internal_error",
}

HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "The request could not be understood.",
    401: "Authentication is required.",
    403: "Your role cannot perform this action.",
    404: "The requested resource was not found.",
    405: "The method is not allowed for this resource.",
    409: "The request conflicts with existing data.",
    413: "The request payload is too large.",
    415: "The request content type is not supported.",
    422: "The request failed validation.",
    429: "Too many requests. Please try again later.",
    500: "The server could not complete the request.",
}


@dataclass(frozen=True, slots=True)
class FieldError:
    """A single field-level validation failure."""

    field: str
    message: str
    code: str = "invalid"

    def as_dict(self) -> FieldDetail:
        """Return the JSON representation used in 422 responses."""
        return {"field": self.field, "message": self.message, "code": self.code}


class ApiError(Exception):
    """An application error carrying an HTTP status and a stable error code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: ErrorDetails = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.status = status_code
        self.code = code
        self.message = message
        self.details = details


FHIR_ISSUE_CODES: frozenset[str] = frozenset(
    {
        "invalid",
        "structure",
        "required",
        "value",
        "login",
        "expired",
        "code-invalid",
        "not-found",
        "duplicate",
        "forbidden",
        "conflict",
        "processing",
        "security",
        "too-long",
        "not-supported",
    }
)

_FHIR_CODE_ALIASES: dict[str, str] = {
    "bad_request": "invalid",
    "unauthorized": "login",
    "invalid_token": "login",
    "revoked": "login",
    "forbidden": "forbidden",
    "not_found": "not-found",
    "not-supported": "not-supported",
    "method_not_allowed": "not-supported",
    "conflict": "conflict",
    "duplicate": "duplicate",
    "payload_too_large": "too-long",
    "unsupported_media_type": "invalid",
    "unprocessable_entity": "invalid",
    "validation_failed": "invalid",
    "too_many_requests": "processing",
    "internal_error": "processing",
    "database_error": "processing",
}


def _is_fhir_request() -> bool:
    """Report whether the current request belongs to the FHIR API."""
    return request.path == "/api/v1/fhir" or request.path.startswith("/api/v1/fhir/")


def fhir_error_response(
    status_code: int,
    code: str,
    message: str,
    details: ErrorDetails = None,
) -> Response:
    """Build the ``OperationOutcome`` response required by the FHIR API."""
    issue_code = _FHIR_CODE_ALIASES.get(code, code)
    if issue_code not in FHIR_ISSUE_CODES:
        issue_code = "processing"
    diagnostics = message
    if isinstance(details, list):
        diagnostics = (
            "; ".join(
                str(item.get("message", message))
                for item in details
                if isinstance(item, dict)
            )
            or message
        )
    payload = {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": issue_code,
                "diagnostics": diagnostics,
            }
        ],
    }
    return Response(
        simplejson.dumps(payload, use_decimal=True, ensure_ascii=False),
        status=status_code,
        content_type="application/fhir+json",
    )


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: ErrorDetails = None,
) -> Response:
    """Build the common error envelope for the current request path."""
    if _is_fhir_request():
        return fhir_error_response(status_code, code, message, details)
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    response = jsonify({"error": error})
    response.status_code = status_code
    return response


def _rollback_session() -> None:
    """Return the scoped database session to a usable state after a DB error."""
    from app.extensions import db

    db.session.rollback()


def register_error_handlers(app: Flask) -> None:
    """Install request IDs, security headers, and JSON error handlers."""

    @app.before_request
    def _assign_request_id() -> None:
        supplied = request.headers.get("X-Request-ID", "").strip()
        g.request_id = supplied[:64] if supplied else uuid.uuid4().hex

    @app.after_request
    def _set_headers(response: Response) -> Response:
        response.headers["X-Request-ID"] = str(getattr(g, "request_id", ""))
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError) -> Response:
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.errorhandler(HTTPException)
    def _handle_http_error(exc: HTTPException) -> Response:
        status = exc.code or 500
        code = HTTP_ERROR_CODES.get(status, "http_error")
        message = HTTP_ERROR_MESSAGES.get(
            status, exc.description or "The request could not be completed."
        )
        if status >= 500:
            message = HTTP_ERROR_MESSAGES[500]
            current_app.logger.exception("Unhandled HTTP error", exc_info=exc)
        return error_response(status, code, message)

    @app.errorhandler(IntegrityError)
    def _handle_integrity_error(exc: IntegrityError) -> Response:
        _rollback_session()
        current_app.logger.warning("Database integrity error: %s", type(exc).__name__)
        return error_response(
            409,
            "conflict",
            "The request conflicts with existing data.",
        )

    @app.errorhandler(SQLAlchemyError)
    def _handle_database_error(exc: SQLAlchemyError) -> Response:
        _rollback_session()
        current_app.logger.exception("Database error", exc_info=exc)
        return error_response(500, "database_error", "The database request failed.")

    @app.errorhandler(Exception)
    def _handle_unexpected_error(exc: Exception) -> Response:
        current_app.logger.exception("Unhandled application error", exc_info=exc)
        return error_response(500, "internal_error", HTTP_ERROR_MESSAGES[500])
