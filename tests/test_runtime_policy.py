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


def test_authentication_never_logs_credential_material():
    text = Path("auth.py").read_text(encoding="utf-8")

    assert "hmac.compare_digest" in text
    assert "key_prefix" not in text
    assert "api_key[:8]" not in text


def test_render_runtime_defaults_to_production_and_validates_secrets():
    config_text = Path("config.py").read_text(encoding="utf-8")
    api_text = Path("api.py").read_text(encoding="utf-8")

    assert '_RENDER_DEFAULT_ENV = "production"' in config_text
    assert "def validate_runtime" in config_text
    assert '"FAP_API_KEY"' in config_text
    assert '"FAP_CORE_API_KEY"' in config_text
    assert "config.validate_runtime()" in api_text
