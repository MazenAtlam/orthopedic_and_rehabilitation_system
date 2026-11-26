"""Unified Flask application factory for the Phase 2 Healthcare API."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from flask import Flask
from flask.json.provider import DefaultJSONProvider
from sqlalchemy import text

from app.api.v1 import api_v1
from app.api.v1.billing import billing
from app.api.v1.fhir import fhir
from app.api.v1.reports import reporting
from app.config import (
    BaseConfig,
    normalize_database_url,
    resolve_config,
    validate_config,
)
from app.errors import register_error_handlers
from app.extensions import db, init_extensions
from app.models import Base as _Base  # noqa: F401  (registers models in metadata)
from scripts.demo_token import install_command as install_demo_token
from scripts.load_icd10 import install_command as install_icd10
from scripts.seed import install_command as install_seed

__all__ = ["HealthcareApp", "JsonProvider", "create_app", "normalize_database_url"]


class JsonProvider(DefaultJSONProvider):
    """Preserve Decimal precision on parse and render UTC ISO-8601 dates."""

    sort_keys = False

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
    """Flask application subclass using the Decimal-aware JSON provider."""

    json_provider_class = JsonProvider


def create_app(
    config_object: str | type[BaseConfig] | None = None,
    *,
    database_url: str | None = None,
    secret: str | None = None,
    demo: bool | None = None,
    **overrides: Any,
) -> HealthcareApp:
    """Build and configure the unified Phase 2 Flask application."""
    app = HealthcareApp(__name__, static_folder=None)
    app.config.from_object(resolve_config(config_object))

    if database_url is not None:
        normalized = normalize_database_url(database_url)
        overrides.setdefault("DATABASE_URL", normalized)
        overrides.setdefault("SQLALCHEMY_DATABASE_URI", normalized)
    elif "SQLALCHEMY_DATABASE_URI" in overrides and isinstance(
        overrides["SQLALCHEMY_DATABASE_URI"], str
    ):
        overrides["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(
            overrides["SQLALCHEMY_DATABASE_URI"]
        )
    else:
        env_url = normalize_database_url(
            str(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
        )
        app.config["DATABASE_URL"] = env_url
        app.config["SQLALCHEMY_DATABASE_URI"] = env_url

    if secret is not None:
        overrides.setdefault("JWT_SECRET_KEY", secret)
    if demo is not None:
        overrides.setdefault(
            "DEMO_MODE", demo and app.config.get("APP_ENV") != "production"
        )

    app.config.update(overrides)
    if app.config.get("APP_ENV") == "production":
        app.config["DEMO_MODE"] = False
    validate_config(app.config)

    register_error_handlers(app)
    init_extensions(app)
    with app.app_context():
        app.extensions["ortho_db"] = db.engine

    app.register_blueprint(api_v1)
    for blueprint in (billing, reporting, fhir):
        app.register_blueprint(blueprint)

    install_seed(app)
    install_demo_token(app)
    install_icd10(app)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app
