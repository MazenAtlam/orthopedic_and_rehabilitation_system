"""CLI helper to generate short-lived demo JWTs."""

from datetime import timedelta

import click
from flask import Flask, current_app
from flask.cli import with_appcontext
from flask_jwt_extended import create_access_token
from sqlalchemy import select

from app.models import User, UserRole
from app.utils.common import db
from scripts.seed import ADMIN, OTHER, PATIENT, PHYSIO, STAFF, THIRD

ACCOUNTS = {
    "admin": (ADMIN, UserRole.admin),
    "staff": (STAFF, UserRole.staff),
    "patient": (PATIENT, UserRole.patient),
    "other": (OTHER, UserRole.patient),
    "physio": (PHYSIO, UserRole.staff),
    "third": (THIRD, UserRole.patient),
}


@click.command("demo-fhir-token")
@click.option("--role", type=click.Choice(tuple(ACCOUNTS)), required=True)
@with_appcontext
def demo_token(role: str) -> None:
    if (
        not current_app.config.get("DEMO_MODE")
        or current_app.config.get("APP_ENV") == "production"
    ):
        raise click.ClickException(
            "This command requires a non-production DEMO_MODE=1 app."
        )
    account, expected_role = ACCOUNTS[role]
    with db().connect() as connection:
        identity = connection.scalar(
            select(User.user_id).where(
                User.email == account,
                User.role == expected_role,
                User.is_active.is_(True),
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
