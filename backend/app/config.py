"""Configuration profiles and startup validation for the Phase 2 API."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import timedelta
from typing import Any, Final, cast

POSTGRES_SCHEMES: Final[tuple[str, ...]] = (
    "postgresql://",
    "postgresql+psycopg://",
    "postgresql+psycopg2://",
)


def normalize_database_url(url: str) -> str:
    """Normalise PostgreSQL connection URLs to use psycopg v3."""
    cleaned = url.strip()
    if cleaned.startswith("postgres://"):
        return "postgresql+psycopg://" + cleaned.removeprefix("postgres://")
    if cleaned.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + cleaned.removeprefix("postgresql+psycopg2://")
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg://" + cleaned.removeprefix("postgresql://")
    return cleaned


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    """Read a positive integer from the environment."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}.")
    return value


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean flag from the environment."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean.")


def _env_list(name: str, default: list[str]) -> list[str]:
    """Read a comma-separated list from the environment."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def database_uri_from_env() -> str:
    """Return the configured PostgreSQL URL normalized for psycopg v3."""
    return normalize_database_url(os.environ.get("DATABASE_URL", ""))


class BaseConfig:
    """Shared settings; secrets and infrastructure values come from the environment."""

    APP_ENV: str = os.environ.get("APP_ENV", "development")
    DEBUG: bool = False
    TESTING: bool = False
    PROPAGATE_EXCEPTIONS: bool = False
    DEMO_MODE: bool = _env_bool("DEMO_MODE", False)

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-only-change-me")
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)

    DATABASE_URL: str = database_uri_from_env()
    SQLALCHEMY_DATABASE_URI: str = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict[str, Any] = {
        "pool_pre_ping": True,
        "connect_args": {"options": "-c timezone=UTC"},
    }

    JWT_TOKEN_LOCATION: list[str] = ["headers", "cookies"]
    JWT_HEADER_NAME: str = "Authorization"
    JWT_HEADER_TYPE: str = "Bearer"
    JWT_ACCESS_COOKIE_NAME: str = "access_token_cookie"
    JWT_REFRESH_COOKIE_NAME: str = "refresh_token_cookie"
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(
        minutes=_env_int("JWT_ACCESS_TOKEN_MINUTES", 15)
    )
    JWT_REFRESH_TOKEN_EXPIRES: timedelta = timedelta(
        days=_env_int("JWT_REFRESH_TOKEN_DAYS", 7)
    )
    JWT_COOKIE_HTTPONLY: bool = True
    JWT_COOKIE_SECURE: bool = _env_bool("JWT_COOKIE_SECURE", False)
    JWT_COOKIE_SAMESITE: str = "Lax"
    JWT_COOKIE_CSRF_PROTECT: bool = False
    JWT_REFRESH_COOKIE_PATH: str = "/api/v1/auth"

    BCRYPT_ROUNDS: int = _env_int("BCRYPT_ROUNDS", 12, minimum=4)

    MAX_CONTENT_LENGTH: int = _env_int("MAX_UPLOAD_BYTES", 52_428_800)
    CORS_ORIGINS: list[str] = _env_list(
        "CORS_ORIGINS",
        ["http://localhost", "http://localhost:5173", "http://localhost:5174"],
    )
    CORS_SUPPORTS_CREDENTIALS: bool = True

    RATELIMIT_ENABLED: bool = _env_bool("RATELIMIT_ENABLED", True)
    RATELIMIT_DEFAULT: str = os.environ.get(
        "RATELIMIT_DEFAULT", "300 per hour, 60 per minute"
    )
    RATELIMIT_STORAGE_URI: str = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    LOGIN_MAX_ATTEMPTS: int = _env_int("MAX_FAILED_LOGINS", 5)
    LOGIN_LOCK_MINUTES: int = _env_int("LOGIN_LOCK_MINUTES", 15)
    LOGIN_ATTEMPT_WINDOW_MINUTES: int = _env_int("LOGIN_ATTEMPT_WINDOW_MINUTES", 15)

    SLOT_START_HOUR: int = _env_int("SLOT_START_HOUR", 8, minimum=0)
    SLOT_END_HOUR: int = _env_int("SLOT_END_HOUR", 18)
    SLOT_MINUTES: int = _env_int("SLOT_MINUTES", 30)

    OHIF_VIEWER_URL: str = os.environ.get(
        "OHIF_VIEWER_URL", "http://localhost:8042/ohif/viewer"
    )


class DevelopmentConfig(BaseConfig):
    """Local development settings."""

    APP_ENV = "development"
    DEBUG = True


class TestingConfig(BaseConfig):
    """Deterministic settings for the Phase 2 test suite."""

    APP_ENV = "testing"
    TESTING = True
    DEBUG = False
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_CSRF_PROTECT = False
    RATELIMIT_ENABLED = False


class ProductionConfig(BaseConfig):
    """Deployment settings with cookies restricted to HTTPS."""

    APP_ENV = "production"
    DEBUG = False
    DEMO_MODE = False
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_CSRF_PROTECT = False


Config = DevelopmentConfig

CONFIG_BY_NAME: Final[dict[str, type[BaseConfig]]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def resolve_config(config: str | type[BaseConfig] | None) -> type[BaseConfig]:
    """Resolve a config name, class or ``APP_ENV`` / ``FLASK_CONFIG``."""
    if config is None:
        config = os.environ.get("FLASK_CONFIG") or os.environ.get(
            "APP_ENV", "development"
        )
    if isinstance(config, str):
        try:
            return CONFIG_BY_NAME[config.lower()]
        except KeyError as exc:
            raise ValueError(f"Unknown configuration profile: {config}") from exc
    if not isinstance(config, type) or not issubclass(config, BaseConfig):
        raise TypeError("config must be a profile name or a BaseConfig subclass.")
    return config


def validate_config(config: Mapping[str, Any]) -> None:
    """Fail fast when a configuration cannot safely start the API."""
    uri = config.get("SQLALCHEMY_DATABASE_URI")
    if not isinstance(uri, str) or not uri.startswith(POSTGRES_SCHEMES):
        raise RuntimeError("SQLALCHEMY_DATABASE_URI must be a PostgreSQL URL.")

    app_env = config.get("APP_ENV", "development")
    secret = config.get("JWT_SECRET_KEY")
    if (
        not isinstance(secret, str)
        or not secret
        or secret.startswith("replace-with-")
        or (app_env == "production" and len(secret.encode("utf-8")) < 32)
    ):
        raise RuntimeError(
            "JWT_SECRET_KEY must be a unique value of at least 32 bytes."
        )

    for key in (
        "LOGIN_MAX_ATTEMPTS",
        "LOGIN_LOCK_MINUTES",
        "LOGIN_ATTEMPT_WINDOW_MINUTES",
    ):
        value = config.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise RuntimeError(f"{key} must be a positive integer.")

    for key in ("SLOT_START_HOUR", "SLOT_END_HOUR", "SLOT_MINUTES"):
        value = config.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise RuntimeError(f"{key} must be a positive integer.")
    start_hour = cast(int, config.get("SLOT_START_HOUR"))
    end_hour = cast(int, config.get("SLOT_END_HOUR"))
    slot_minutes = cast(int, config.get("SLOT_MINUTES"))
    if start_hour >= end_hour or end_hour > 24:
        raise RuntimeError("SLOT_END_HOUR must be after SLOT_START_HOUR and <= 24.")
    if not 0 < slot_minutes <= 1440:
        raise RuntimeError("SLOT_MINUTES must be between 1 and 1440.")
    if ((end_hour - start_hour) * 60) % slot_minutes != 0:
        raise RuntimeError("The clinic day must divide evenly into SLOT_MINUTES.")

    origins = config.get("CORS_ORIGINS")
    if not isinstance(origins, list) or not all(
        isinstance(item, str) for item in origins
    ):
        raise RuntimeError("CORS_ORIGINS must be a list of strings.")
    if app_env == "production" and not origins:
        raise RuntimeError("Production deployments must define CORS_ORIGINS.")
    if app_env == "production" and not config.get("JWT_COOKIE_SECURE"):
        raise RuntimeError("Production deployments require secure JWT cookies.")
