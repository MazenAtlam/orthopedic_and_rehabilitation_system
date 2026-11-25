from datetime import timedelta

import click
from flask import Flask, current_app
from flask.cli import with_appcontext
from flask_jwt_extended import create_access_token
from sqlalchemy import select

from app.models.schema_v1 import user
from app.utils.common import db
from scripts.seed import ADMIN, OTHER, PATIENT, PHYSIO, STAFF, THIRD

ACCOUNTS = {
    "admin": (ADMIN, "admin"),
    "staff": (STAFF, "staff"),
    "patient": (PATIENT, "patient"),
    "other": (OTHER, "patient"),
    "physio": (PHYSIO, "staff"),
    "third": (THIRD, "patient"),
}


@click.command("demo-fhir-token")
@click.option("--role", type=click.Choice(tuple(ACCOUNTS)), required=True)
@with_appcontext
def demo_token(role: str) -> None:
    if (
        not current_app.config["DEMO_MODE"]
        or current_app.config["APP_ENV"] == "production"
    ):
        raise click.ClickException(
            "This command requires a non-production DEMO_MODE=1 app."
        )
    account, expected_role = ACCOUNTS[role]
    with db().connect() as connection:
        identity = connection.scalar(
            select(user.c.user_id).where(
                user.c.email == account, user.c.role == expected_role, user.c.is_active
            )
        )
    if identity is None:
        raise click.ClickException("Seed the fictional demo accounts first.")
    token = create_access_token(
        identity=str(identity), expires_delta=timedelta(minutes=15)
    )
    click.echo(token)


def install_command(app: Flask) -> None:
    app.cli.add_command(demo_token)
