"""Load the WHO ICD-10 2019 English orthopedic release (manual or startup ensure)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import tempfile
import urllib.error
import urllib.request
from io import TextIOWrapper
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import click
from flask import Flask
from flask.cli import with_appcontext
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from app import normalize_database_url
from app.models import Icd10Code
from app.utils.common import db

MEMBER = "icd102019syst_codes.txt"
ARCHIVE_NAME = "icd102019enMeta.zip"
WHO_ARCHIVE_URL = f"https://icdcdn.who.int/icd10/meta/{ARCHIVE_NAME}"
ARCHIVE_SHA256 = "a9fa787fa79076e199e46ca645bbc076449853e93e62cd3b2050b96dc96bbc1d"
EXPECTED_COUNT = 679
CODE = re.compile(r"(?:M[0-9]{2}|S[1-9][23])(?:\.[0-9A-Z]{1,4})?")


def default_archive_path() -> Path:
    configured = os.environ.get("ICD10_ARCHIVE_PATH", "").strip()
    if configured:
        return Path(configured)
    docker_mount = Path("/app/database_seed") / ARCHIVE_NAME
    if docker_mount.parent.exists():
        return docker_mount
    return Path(__file__).resolve().parents[2] / "database" / "seed" / ARCHIVE_NAME


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
    if len(entries) != EXPECTED_COUNT:
        raise ValueError(f"Expected {EXPECTED_COUNT} orthopedic WHO ICD-10 entries.")
    return list(entries.values())


def load_codes(engine: Engine, codes: list[dict[str, str]]) -> None:
    with engine.begin() as connection:
        statement = insert(Icd10Code).values(codes)
        connection.execute(
            statement.on_conflict_do_update(
                index_elements=[Icd10Code.code],
                set_={
                    "description": statement.excluded.description,
                    "category": statement.excluded.category,
                },
            )
        )


def _has_valid_checksum(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with path.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest() == ARCHIVE_SHA256
    except OSError:
        return False


def download_who_archive(target: Path, url: str = WHO_ARCHIVE_URL) -> Path:
    request = urllib.request.Request(
        url, headers={"User-Agent": "HCIS-Orthopedic-ICD10-Loader/1.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    if hashlib.sha256(payload).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Downloaded WHO ICD-10 archive failed SHA-256 verification.")

    for candidate in (target, Path(tempfile.gettempdir()) / ARCHIVE_NAME):
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            temp_file = candidate.with_suffix(".tmp")
            temp_file.write_bytes(payload)
            temp_file.replace(candidate)
            return candidate
        except OSError:
            continue
    raise OSError("Unable to write downloaded WHO ICD-10 archive to disk.")


def ensure_catalog_loaded(
    engine: Engine,
    archive_path: Path | None = None,
    *,
    url: str = WHO_ARCHIVE_URL,
) -> int:
    with engine.connect() as connection:
        existing = connection.scalar(select(func.count()).select_from(Icd10Code)) or 0
    if existing >= EXPECTED_COUNT:
        return 0

    target = archive_path or default_archive_path()
    resolved = target if _has_valid_checksum(target) else None
    if resolved is None:
        fallback = Path(tempfile.gettempdir()) / ARCHIVE_NAME
        if _has_valid_checksum(fallback):
            resolved = fallback
        else:
            resolved = download_who_archive(target, url=url)

    codes = read_orthopedic_codes(resolved)
    load_codes(engine, codes)
    return len(codes)


@click.command("load-icd10")
@click.option(
    "--archive",
    required=False,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to local WHO icd102019enMeta.zip archive.",
)
@click.option(
    "--ensure",
    is_flag=True,
    default=False,
    help="Idempotently ensure all 679 WHO orthopedic codes are loaded.",
)
@with_appcontext
def load_icd10(archive: Path | None, ensure: bool) -> None:
    if ensure:
        try:
            loaded = ensure_catalog_loaded(db(), archive)
        except (
            BadZipFile,
            OSError,
            urllib.error.URLError,
            ValueError,
            KeyError,
            csv.Error,
        ) as error:
            click.echo(
                f"[icd10] Warning: could not preload full WHO catalogue ({error}). "
                "Continuing with seeded ICD-10 entries."
            )
            return
        if loaded == 0:
            click.echo(
                f"[icd10] WHO ICD-10 catalogue already present (>={EXPECTED_COUNT})."
            )
        else:
            click.echo(
                f"[icd10] Loaded {loaded} WHO ICD-10 orthopedic codes (2019 English)."
            )
        return

    if archive is None:
        raise click.ClickException("Supply --archive <path> or --ensure.")
    try:
        codes = read_orthopedic_codes(archive)
    except (BadZipFile, OSError, ValueError, KeyError, csv.Error) as error:
        raise click.ClickException(str(error)) from error
    load_codes(db(), codes)
    click.echo(f"Loaded {len(codes)} WHO ICD-10 orthopedic codes (2019 English).")


def install_command(app: Flask) -> None:
    app.cli.add_command(load_icd10)


def main() -> None:
    parser = argparse.ArgumentParser(description="WHO ICD-10 orthopedic loader.")
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--ensure", action="store_true")
    args = parser.parse_args()

    raw_url = os.environ.get("DATABASE_URL")
    if not raw_url:
        raise SystemExit("DATABASE_URL is required.")
    engine = create_engine(normalize_database_url(raw_url))
    try:
        if args.ensure:
            try:
                loaded = ensure_catalog_loaded(engine, args.archive)
            except (
                BadZipFile,
                OSError,
                urllib.error.URLError,
                ValueError,
                KeyError,
                csv.Error,
            ) as error:
                print(
                    "[icd10] Warning: could not preload full WHO catalogue "
                    f"({error}). Continuing with seeded ICD-10 entries."
                )
                return
            if loaded == 0:
                print(
                    "[icd10] WHO ICD-10 catalogue already present "
                    f"(>={EXPECTED_COUNT})."
                )
            else:
                print(
                    f"[icd10] Loaded {loaded} WHO ICD-10 orthopedic codes "
                    "(2019 English)."
                )
        else:
            if args.archive is None:
                raise SystemExit("Supply --archive <path> or --ensure.")
            codes = read_orthopedic_codes(args.archive)
            load_codes(engine, codes)
            print(f"Loaded {len(codes)} WHO ICD-10 orthopedic codes (2019 English).")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
