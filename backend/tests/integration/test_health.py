"""Smoke test: the API is alive."""

from flask.testing import FlaskClient


def test_health_returns_ok(client: FlaskClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
