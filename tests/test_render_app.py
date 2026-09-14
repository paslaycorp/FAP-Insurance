"""Production entrypoint contract tests."""

from fastapi.testclient import TestClient

from render_app import app


def test_render_root_get_is_ready():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json()["service"] == "fap-insurance"
    assert response.json()["status"] == "ready"
    assert response.json()["health"] == "/health"


def test_render_root_head_is_ready():
    with TestClient(app) as client:
        response = client.head("/")

    assert response.status_code == 200
    assert response.headers["X-FAP-Service"] == "fap-insurance"
