import os
from secrets import token_hex

import pytest
from alembic import command
from alembic.config import Config
from flask_jwt_extended import create_access_token
from sqlalchemy import create_engine, inspect, select

from app import create_app, normalize_database_url
from app.models.schema_v1 import metadata, user
from scripts.seed import ADMIN, OTHER, PATIENT, STAFF, seed


@pytest.fixture(scope="session")
def app():
    raw_url = os.environ.get("ORTHO_TEST_DATABASE_URL") or (
        os.environ.get("DATABASE_URL")
        if os.environ.get("APP_ENV") == "testing"
        else None
    )
    if not raw_url:
        pytest.skip(
            "Set ORTHO_TEST_DATABASE_URL to a dedicated empty PostgreSQL database."
        )
    url = normalize_database_url(raw_url)
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    if tables.intersection(set(metadata.tables) | {"alembic_version"}):
        pytest.fail(
            "The test database already contains healthcare tables. Use an empty test database."
        )

    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("DATABASE_URL", url)
        command.upgrade(Config("alembic.ini"), "head")
    application = create_app(
        database_url=url,
        secret=token_hex(32),
        demo=True,
    )
    application.config["TESTING"] = True
    engine = application.extensions["ortho_db"]
    assert seed(engine) is True
    assert seed(engine) is False
    yield application
    engine.dispose()


@pytest.fixture(scope="session")
def tokens(app):
    engine = app.extensions["ortho_db"]
    accounts = {"admin": ADMIN, "staff": STAFF, "patient": PATIENT, "other": OTHER}
    with app.app_context(), engine.connect() as connection:
        ids = dict(
            connection.execute(
                select(user.c.email, user.c.user_id).where(
                    user.c.email.in_(accounts.values()),
                )
            )
            .tuples()
            .all()
        )
        return {
            key: {
                "Authorization": f"Bearer {create_access_token(identity=str(ids[email]))}"
            }
            for key, email in accounts.items()
        }


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def people(app, tokens):
    with app.test_client() as client:
        patients = [
            client.get("/api/v1/fhir/Patient", headers=tokens[key]).json["entry"][0][
                "resource"
            ]["id"]
            for key in ("patient", "other")
        ]
        staff = client.get("/api/v1/fhir/Practitioner", headers=tokens["staff"]).json
    return (*map(int, patients), int(staff["entry"][0]["resource"]["id"]))
