import os
from datetime import date, datetime, timezone
from decimal import Decimal

from flask import Flask, request
from flask.json.provider import DefaultJSONProvider
from flask_jwt_extended import JWTManager
from sqlalchemy import create_engine, text
from werkzeug.exceptions import HTTPException

from ortho.billing import billing
from ortho.common import ApiError
from ortho.demo_token import install_command as install_demo_token
from ortho.fhir import fhir, fhir_error
from ortho.load_icd10 import install_command as install_icd10
from ortho.records import records
from ortho.reports import reporting
from ortho.seed import install_command


class JsonProvider(DefaultJSONProvider):
    def loads(self, data, **kwargs):
        kwargs.setdefault("parse_float", Decimal)
        return super().loads(data, **kwargs)

    @staticmethod
    def default(value):
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if isinstance(value, date):
            return value.isoformat()
        return DefaultJSONProvider.default(value)


class HealthcareApp(Flask):
    json_provider_class = JsonProvider


def create_app(*, database_url=None, secret=None, demo=None):
    url = database_url or os.environ.get("DATABASE_URL", "")
    secret = secret or os.environ.get("JWT_SECRET_KEY", "")
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("Set DATABASE_URL to a postgresql+psycopg connection URL.")
    if len(secret.encode()) < 32 or secret.startswith("replace-with-"):
        raise RuntimeError("Set JWT_SECRET_KEY to a unique value of at least 32 bytes.")

    app = HealthcareApp(__name__, static_folder=None)
    app.config.update(
        APP_ENV=os.environ.get("APP_ENV", "development"),
        JWT_SECRET_KEY=secret,
        JWT_TOKEN_LOCATION=["headers"],
        MAX_CONTENT_LENGTH=1_048_576,
        DEMO_MODE=demo if demo is not None else os.environ.get("DEMO_MODE") == "1",
    )
    app.extensions["ortho_db"] = create_engine(
        url, pool_pre_ping=True, connect_args={"options": "-c timezone=UTC"}
    )
    jwt = JWTManager(app)
    for blueprint in (billing, records, reporting, fhir):
        app.register_blueprint(blueprint)
    install_command(app)
    install_demo_token(app)
    install_icd10(app)

    def failure(status, code, message):
        path = request.path
        if path == "/api/v1/fhir" or path.startswith("/api/v1/fhir/"):
            return fhir_error(status, code, message)
        return {"error": {"code": code, "message": message}}, status

    @app.errorhandler(ApiError)
    def api_error(error):
        return failure(error.status, error.code, error.message)

    @app.errorhandler(HTTPException)
    def http_error(error):
        codes = {404: "not-found", 405: "not-supported", 413: "too-long", 415: "invalid"}
        return failure(error.code, codes.get(error.code, "processing"), error.description)

    @jwt.unauthorized_loader
    def token_missing(_reason):
        return failure(401, "login", "A valid bearer access token is required.")

    @jwt.invalid_token_loader
    def token_invalid(_reason):
        return failure(401, "login", "The access token is invalid.")

    @jwt.expired_token_loader
    def token_expired(_header, _payload):
        return failure(401, "expired", "The access token has expired.")

    @app.after_request
    def headers(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/healthz")
    def health():
        with app.extensions["ortho_db"].connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app
