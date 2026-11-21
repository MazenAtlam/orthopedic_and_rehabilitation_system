import os

import pytest
from sqlalchemy import func, select

from ortho.schema_v1 import icd10_code
from ortho.load_icd10 import read_orthopedic_codes


def test_rejects_unrecognized_archive(tmp_path):
    archive = tmp_path / "icd10.zip"
    archive.write_bytes(b"not the WHO archive")
    with pytest.raises(ValueError, match="official WHO"):
        read_orthopedic_codes(archive)


def test_demo_tokens_are_role_bound_and_disabled_outside_demo(app, client):
    runner = app.test_cli_runner()
    token = runner.invoke(args=["demo-fhir-token", "--role", "patient"])
    assert token.exit_code == 0, token.output
    headers = {"Authorization": f"Bearer {token.output.strip()}"}
    assert client.get("/api/v1/fhir/Patient", headers=headers).json["total"] == 1
    assert client.get("/api/v1/fhir/metadata", headers=headers).status_code == 403

    with pytest.MonkeyPatch.context() as config:
        config.setitem(app.config, "DEMO_MODE", False)
        assert runner.invoke(args=["demo-fhir-token", "--role", "staff"]).exit_code == 1
        config.setitem(app.config, "DEMO_MODE", True)
        config.setitem(app.config, "APP_ENV", "production")
        assert runner.invoke(args=["demo-fhir-token", "--role", "staff"]).exit_code == 1


def test_official_catalog_is_repeatable_and_searchable(app, client, tokens):
    path = os.environ.get("HCIS_ICD10_TEST_ARCHIVE")
    if not path:
        pytest.skip(
            "Supply the locally obtained WHO archive to check the official import."
        )
    runner = app.test_cli_runner()
    for _ in range(2):
        result = runner.invoke(args=["load-icd10", "--archive", path])
        assert result.exit_code == 0, result.output
        assert "Loaded 679" in result.output

    with app.extensions["ortho_db"].connect() as connection:
        assert connection.scalar(select(func.count()).select_from(icd10_code)) >= 679
    result = client.get("/api/v1/icd10?q=M16.1", headers=tokens["staff"])
    assert result.status_code == 200
    assert "M16.1" in result.get_data(as_text=True)
