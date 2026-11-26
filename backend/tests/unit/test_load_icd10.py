"""Unit tests for the idempotent WHO ICD-10 startup loader."""

from __future__ import annotations

import hashlib
import urllib.error
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine

from app.models import Icd10Code
from scripts import load_icd10 as loader


def test_ensure_skips_when_catalog_already_populated(tmp_path: Path) -> None:
    engine = create_engine("sqlite://")
    Icd10Code.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(
            Icd10Code.__table__.insert(),
            [
                {
                    "code": f"M{index // 10:02d}.{index % 10}",
                    "description": f"Condition {index}",
                    "category": "Musculoskeletal",
                }
                for index in range(loader.EXPECTED_COUNT)
            ],
        )

    assert loader.ensure_catalog_loaded(engine, tmp_path / "missing.zip") == 0
    engine.dispose()


def test_download_who_archive_rejects_bad_checksum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"corrupted-archive-bytes"

    monkeypatch.setattr(
        loader.urllib.request, "urlopen", lambda *_a, **_kw: FakeResponse()
    )
    with pytest.raises(ValueError, match="SHA-256"):
        loader.download_who_archive(tmp_path / "icd102019enMeta.zip")


def test_download_who_archive_caches_verified_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"verified-test-payload"
    expected_hash = hashlib.sha256(payload).hexdigest()

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return payload

    monkeypatch.setattr(loader, "ARCHIVE_SHA256", expected_hash)
    monkeypatch.setattr(
        loader.urllib.request, "urlopen", lambda *_a, **_kw: FakeResponse()
    )
    target = tmp_path / "seed" / "icd102019enMeta.zip"
    saved = loader.download_who_archive(target)
    assert saved == target
    assert target.read_bytes() == payload


def test_ensure_loads_downloaded_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine("sqlite://")
    Icd10Code.__table__.create(engine)
    fake_zip = tmp_path / "icd102019enMeta.zip"
    fake_zip.write_bytes(b"cached")
    captured: list[dict[str, str]] = []

    monkeypatch.setattr(loader, "_has_valid_checksum", lambda p: p == fake_zip)
    monkeypatch.setattr(
        loader,
        "read_orthopedic_codes",
        lambda _p: [
            {"code": "M17.9", "description": "Knee OA", "category": "Musculoskeletal"}
        ],
    )

    def fake_load(_eng: Any, codes: list[dict[str, str]]) -> None:
        captured.extend(codes)

    monkeypatch.setattr(loader, "load_codes", fake_load)
    count = loader.ensure_catalog_loaded(engine, fake_zip)
    assert count == 1
    assert captured[0]["code"] == "M17.9"
    engine.dispose()


def test_cli_ensure_handles_offline_failure_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app as app_module

    monkeypatch.setattr(app_module, "validate_config", lambda _cfg: None)
    app = app_module.create_app(
        "testing",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_ENGINE_OPTIONS={},
        JWT_SECRET_KEY="k" * 40,
    )
    monkeypatch.setattr(
        loader,
        "ensure_catalog_loaded",
        lambda *_a, **_kw: (_ for _ in ()).throw(urllib.error.URLError("offline")),
    )
    result = app.test_cli_runner().invoke(args=["load-icd10", "--ensure"])
    assert result.exit_code == 0
    assert "Warning: could not preload" in result.output
