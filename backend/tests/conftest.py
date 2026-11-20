"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app


@pytest.fixture()
def app() -> Iterator[Flask]:
    application = create_app()
    application.config.update(TESTING=True)
    yield application


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()
