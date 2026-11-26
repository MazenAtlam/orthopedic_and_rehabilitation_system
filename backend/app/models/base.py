"""Declarative base shared by the ORM and Alembic metadata."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Root of the Phase 2 model registry."""
