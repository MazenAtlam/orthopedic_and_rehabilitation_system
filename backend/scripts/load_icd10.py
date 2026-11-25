"""Load an independently obtained WHO ICD-10 2019 English release."""

import csv
import hashlib
import re
from io import TextIOWrapper
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import click
from flask import Flask
from flask.cli import with_appcontext
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from app.models.schema_v1 import icd10_code
from app.utils.common import db

MEMBER = "icd102019syst_codes.txt"
ARCHIVE_SHA256 = "a9fa787fa79076e199e46ca645bbc076449853e93e62cd3b2050b96dc96bbc1d"
CODE = re.compile(r"(?:M[0-9]{2}|S[1-9][23])(?:\.[0-9A-Z]{1,4})?")


def read_orthopedic_codes(archive: Path) -> list[dict[str, str]]:
    with archive.open("rb") as data:
        if hashlib.file_digest(data, "sha256").hexdigest() != ARCHIVE_SHA256:
            raise ValueError(
                "Expected the official WHO ICD-10 2019 English metadata ZIP."
            )
        data.seek(0)
        with (
            ZipFile(data) as source,
            TextIOWrapper(source.open(MEMBER), encoding="cp1252", newline="") as codes,
        ):
            entries: dict[str, dict[str, str]] = {}
            for row in csv.reader(codes, delimiter=";"):
                if not row:
                    continue
                if len(row) < 9:
                    raise ValueError("Malformed WHO ICD-10 row.")
                code = row[6].strip()
                if row[1] != "T" or not CODE.fullmatch(code):
                    continue
                description = row[8].strip()
                if not description or code in entries:
                    raise ValueError(f"Invalid or duplicate WHO ICD-10 code {code}.")
                entries[code] = {
                    "code": code,
                    "description": description,
                    "category": "Musculoskeletal" if code.startswith("M") else "Injury",
                }
    if len(entries) != 679:
        raise ValueError("Expected 679 orthopedic WHO ICD-10 entries.")
    return list(entries.values())


def load_codes(engine: Engine, codes: list[dict[str, str]]) -> None:
    with engine.begin() as connection:
        statement = insert(icd10_code).values(codes)
        connection.execute(
            statement.on_conflict_do_update(
                index_elements=[icd10_code.c.code],
                set_={
                    "description": statement.excluded.description,
                    "category": statement.excluded.category,
                },
            )
        )


@click.command("load-icd10")
@click.option(
    "--archive", required=True, type=click.Path(dir_okay=False, path_type=Path)
)
@with_appcontext
def load_icd10(archive: Path) -> None:
    try:
        codes = read_orthopedic_codes(archive)
    except (BadZipFile, OSError, ValueError, KeyError, csv.Error) as error:
        raise click.ClickException(str(error)) from error
    load_codes(db(), codes)
    click.echo(f"Loaded {len(codes)} WHO ICD-10 orthopedic codes (2019 English).")


def install_command(app: Flask) -> None:
    app.cli.add_command(load_icd10)
