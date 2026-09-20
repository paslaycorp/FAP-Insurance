from pathlib import Path

DOCKERFILE = Path("Dockerfile")


def test_container_python_patch_is_fixed():
    text = DOCKERFILE.read_text(encoding="utf-8")

    assert text.count("FROM python:3.12.14-slim") == 2
    assert "FROM python:3.12-slim" not in text
    assert '"pip==26.2.1"' in text


def test_container_healthcheck_is_process_liveness_only():
    text = DOCKERFILE.read_text(encoding="utf-8")

    assert "/live" in text
    assert "urlopen('http://localhost:' + os.environ.get('PORT', '8000') + '/health')" not in text
