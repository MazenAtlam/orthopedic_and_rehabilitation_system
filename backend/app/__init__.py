"""Flask application factory.

Connects Amr's Phase 2 contribution (database, billing, reports, FHIR, demo seed)
to the team backend package (CORS, ``/api/v1/health``, ``/healthz``).
"""

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from flask import Flask, Response, request
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from sqlalchemy import create_engine, text
from werkzeug.exceptions import HTTPException

from app.api.v1.billing import billing
from app.api.v1.fhir import fhir, fhir_error
from app.api.v1.reports import reporting
from app.config import Config
from app.utils.common import ApiError
from scripts.demo_token import install_command as install_demo_token
from scripts.load_icd10 import install_command as install_icd10
from scripts.seed import install_command


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql+psycopg2://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


class JsonProvider(DefaultJSONProvider):
    def loads(self, s: str | bytes, **kwargs: Any) -> Any:
        kwargs.setdefault("parse_float", Decimal)
        return super().loads(s, **kwargs)

    @staticmethod
    def default(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if isinstance(value, date):
            return value.isoformat()
        return DefaultJSONProvider.default(value)


class HealthcareApp(Flask):
    json_provider_class = JsonProvider


def create_app(
    *,
    database_url: str | None = None,
    secret: str | None = None,
    demo: bool | None = None,
) -> HealthcareApp:
    app_env = os.environ.get("APP_ENV", Config.APP_ENV)
    url = normalize_database_url(database_url or os.environ.get("DATABASE_URL", ""))
    secret = secret or os.environ.get("JWT_SECRET_KEY", Config.JWT_SECRET_KEY)
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("Set DATABASE_URL to a postgresql+psycopg connection URL.")
    if (
        not secret
        or secret.startswith("replace-with-")
        or (app_env == "production" and len(secret.encode()) < 32)
    ):
        raise RuntimeError("Set JWT_SECRET_KEY to a unique value of at least 32 bytes.")

    app = HealthcareApp(__name__, static_folder=None)
    app.config.from_object(Config)
    app.config.update(
        APP_ENV=app_env,
        DATABASE_URL=url,
        JWT_SECRET_KEY=secret,
        JWT_TOKEN_LOCATION=["headers"],
        MAX_CONTENT_LENGTH=1_048_576,
        DEMO_MODE=app_env != "production"
        and (demo if demo is not None else os.environ.get("DEMO_MODE") == "1"),
    )
    CORS(app, origins=app.config["CORS_ORIGINS"])
    app.extensions["ortho_db"] = create_engine(
        url, pool_pre_ping=True, connect_args={"options": "-c timezone=UTC"}
    )
    jwt = JWTManager(app)
    for blueprint in (billing, reporting, fhir):
        app.register_blueprint(blueprint)
    install_command(app)
    install_demo_token(app)
    install_icd10(app)

    def failure(status: int, code: str, message: str) -> Any:
        path = request.path
        if path == "/api/v1/fhir" or path.startswith("/api/v1/fhir/"):
            return fhir_error(status, code, message)
        return {"error": {"code": code, "message": message}}, status

    @app.errorhandler(ApiError)
    def api_error(error: ApiError) -> Any:
        return failure(error.status, error.code, error.message)

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException) -> Any:
        codes = {
            404: "not-found",
            405: "not-supported",
            413: "too-long",
            415: "invalid",
        }
        status = error.code or 500
        return failure(
            status,
            codes.get(status, "processing"),
            error.description or "Request failed.",
        )

    @jwt.unauthorized_loader
    def token_missing(_reason: str) -> Any:
        return failure(401, "login", "A valid bearer access token is required.")

    @jwt.invalid_token_loader
    def token_invalid(_reason: str) -> Any:
        return failure(401, "login", "The access token is invalid.")

    @jwt.expired_token_loader
    def token_expired(_header: dict[str, Any], _payload: dict[str, Any]) -> Any:
        return failure(401, "expired", "The access token has expired.")

    @app.after_request
    def headers(response: Response) -> Response:
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        with app.extensions["ortho_db"].connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app
