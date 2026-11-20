"""Application settings read from environment variables."""

import os


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Config:
    """Default configuration. Values come from the .env file."""

    APP_ENV: str = os.getenv("APP_ENV", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-change-me")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    CORS_ORIGINS: list[str] = _split_csv(
        os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:5173")
    )
