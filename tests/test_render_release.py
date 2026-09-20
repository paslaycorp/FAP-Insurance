"""Tests for the fail-closed Render production release controller."""
from __future__ import annotations

import json

import httpx
import pytest

from ops.render_release import (
    EXPECTED_BRANCH,
    EXPECTED_EPM_VERSION,
    EXPECTED_FAP_VERSION,
    EXPECTED_HEALTH_CHECK_PATH,
    EXPECTED_ENVIRONMENT,
    EXPECTED_FAP_CORE_ENVIRONMENT,
    EXPECTED_FAP_CORE_REPO,
    EXPECTED_FAP_CORE_SERVICE,
    EXPECTED_REPO_SLUG,
    RenderAPI,
    deploy_commit_sha,
    read_epm_pin,
    verify_dependency_preflight,
    verify_rollback_health,
    verify_runtime_health,
    wait_for_live,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = json.dumps(payload).encode()

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("failed", request=request, response=response)

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, path, **kwargs):
        self.requests.append((method, path, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        return self.responses.pop(0)


def test_deploy_commit_sha():
    assert deploy_commit_sha({"commit": {"id": "a" * 40}}) == "a" * 40
    assert deploy_commit_sha(None) is None


def test_list_deploys_unwraps_render_cursor_shape():
    client = FakeClient(
        [FakeResponse([{"cursor": "abc", "deploy": {"id": "dep-1", "status": "live"}}])]
    )
    api = RenderAPI("token", "srv-1", client=client)
    assert api.list_deploys() == [{"id": "dep-1", "status": "live"}]


def test_set_health_check_path_uses_bounded_service_patch():
    payload = {
        "id": "srv-1",
        "serviceDetails": {"healthCheckPath": EXPECTED_HEALTH_CHECK_PATH},
    }
    client = FakeClient([FakeResponse(payload)])
    api = RenderAPI("token", "srv-1", client=client)

    assert api.set_health_check_path(EXPECTED_HEALTH_CHECK_PATH) == payload
    assert client.requests == [
        (
            "PATCH",
            "/services/srv-1",
            {"json": {"serviceDetails": {"healthCheckPath": EXPECTED_HEALTH_CHECK_PATH}}},
        )
    ]


def test_wait_for_live_accepts_only_live():
    class API:
        def __init__(self):
            self.states = iter([
                {"id": "dep-1", "status": "build_in_progress"},
                {"id": "dep-1", "status": "update_in_progress"},
                {"id": "dep-1", "status": "live", "commit": {"id": "a" * 40}},
            ])

        def get_deploy(self, deploy_id):
            return next(self.states)

    result = wait_for_live(API(), "dep-1", interval_seconds=0, sleep=lambda _: None)
    assert result["status"] == "live"


def test_wait_for_live_fails_closed_on_terminal_failure():
    class API:
        def get_deploy(self, deploy_id):
            return {"id": deploy_id, "status": "build_failed"}

    with pytest.raises(RuntimeError, match="build_failed"):
        wait_for_live(API(), "dep-1", interval_seconds=0, sleep=lambda _: None)


def test_read_epm_pin(tmp_path):
    sha = "8" * 40
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "epm-evidentiary-provenance-model @ "
        "git+https://github.com/paslaycorp/EPM---EVIDENTIARY-PROVENANCE-MODEL-.git@"
        f"{sha}\n",
        encoding="utf-8",
    )
    assert read_epm_pin(requirements) == sha


def test_dependency_preflight_requires_repeatable_success():
    expected_sha = "c" * 40
    payload = {
        "status": "healthy",
        "service": EXPECTED_FAP_CORE_SERVICE,
        "git_commit": expected_sha,
        "git_repo_slug": EXPECTED_FAP_CORE_REPO,
        "environment": EXPECTED_FAP_CORE_ENVIRONMENT,
    }
    client = FakeClient([FakeResponse(payload), FakeResponse(payload)])
    proof = verify_dependency_preflight(
        "https://fap-core.example/health",
        expected_sha,
        max_attempts=2,
        required_successes=2,
        interval_seconds=0,
        client=client,
        sleep=lambda _: None,
    )
    assert proof["verified"] is True
    assert [item["status_code"] for item in proof["observations"]] == [200, 200]


def test_dependency_preflight_rejects_edge_429_before_deploy():
    client = FakeClient(
        [
            FakeResponse({"detail": "rate limited"}, status_code=429),
            FakeResponse({"detail": "rate limited"}, status_code=429),
            FakeResponse({"detail": "rate limited"}, status_code=429),
        ]
    )
    with pytest.raises(RuntimeError, match="dependency preflight failed"):
        verify_dependency_preflight(
            "https://fap-core.example/health",
            "d" * 40,
            max_attempts=3,
            required_successes=2,
            interval_seconds=0,
            client=client,
            sleep=lambda _: None,
        )


def test_rollback_health_proves_prior_sha_without_current_epm_version_binding():
    sha = "7" * 40
    payload = {
        "status": "healthy",
        "service": "fap-insurance",
        "version": "older-version-is-allowed-for-rollback-proof",
        "epm_engine_version": "older-epm-is-allowed-for-rollback-proof",
        "git_commit": sha,
        "git_branch": EXPECTED_BRANCH,
        "git_repo_slug": EXPECTED_REPO_SLUG,
        "fap_core_connected": True,
    }
    client = FakeClient([FakeResponse(payload)])
    assert verify_rollback_health(
        "https://example.test/health",
        sha,
        timeout_seconds=1,
        interval_seconds=0,
        client=client,
        sleep=lambda _: None,
    ) == payload


def test_runtime_health_proves_exact_release():
    sha = "9" * 40
    core_sha = "8" * 40
    payload = {
        "status": "healthy",
        "service": "fap-insurance",
        "version": EXPECTED_FAP_VERSION,
        "epm_engine_version": EXPECTED_EPM_VERSION,
        "git_commit": sha,
        "git_branch": EXPECTED_BRANCH,
        "git_repo_slug": EXPECTED_REPO_SLUG,
        "fap_core_connected": True,
        "environment": EXPECTED_ENVIRONMENT,
        "fap_core_service": EXPECTED_FAP_CORE_SERVICE,
        "fap_core_git_commit": core_sha,
        "fap_core_git_repo_slug": EXPECTED_FAP_CORE_REPO,
    }
    client = FakeClient([FakeResponse(payload)])
    assert verify_runtime_health(
        "https://example.test/health",
        sha,
        core_sha,
        timeout_seconds=1,
        interval_seconds=0,
        client=client,
        sleep=lambda _: None,
    ) == payload


def test_runtime_health_rejects_wrong_sha(monkeypatch):
    wanted = "a" * 40
    core_sha = "c" * 40
    payload = {
        "status": "healthy",
        "service": "fap-insurance",
        "version": EXPECTED_FAP_VERSION,
        "epm_engine_version": EXPECTED_EPM_VERSION,
        "git_commit": "b" * 40,
        "git_branch": EXPECTED_BRANCH,
        "git_repo_slug": EXPECTED_REPO_SLUG,
        "fap_core_connected": True,
        "environment": EXPECTED_ENVIRONMENT,
        "fap_core_service": EXPECTED_FAP_CORE_SERVICE,
        "fap_core_git_commit": core_sha,
        "fap_core_git_repo_slug": EXPECTED_FAP_CORE_REPO,
    }
    client = FakeClient([FakeResponse(payload)])
    ticks = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr("ops.render_release.time.monotonic", lambda: next(ticks))

    with pytest.raises(RuntimeError, match="commit"):
        verify_runtime_health(
            "https://example.test/health",
            wanted,
            core_sha,
            timeout_seconds=1,
            interval_seconds=0,
            client=client,
            sleep=lambda _: None,
        )


def test_dependency_preflight_rejects_wrong_runtime_identity(monkeypatch):
    wanted = "1" * 40
    payload = {
        "status": "healthy",
        "service": EXPECTED_FAP_CORE_SERVICE,
        "git_commit": "2" * 40,
        "git_repo_slug": EXPECTED_FAP_CORE_REPO,
        "environment": EXPECTED_FAP_CORE_ENVIRONMENT,
    }
    client = FakeClient([FakeResponse(payload)])
    ticks = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr("ops.render_release.time.monotonic", lambda: next(ticks))

    with pytest.raises(RuntimeError, match="dependency preflight failed"):
        verify_dependency_preflight(
            "https://fap-core.example/health",
            wanted,
            max_attempts=1,
            required_successes=1,
            interval_seconds=0,
            client=client,
            sleep=lambda _: None,
        )


def test_runtime_health_rejects_wrong_fap_core_sha(monkeypatch):
    sha = "3" * 40
    wanted_core = "4" * 40
    payload = {
        "status": "healthy",
        "service": "fap-insurance",
        "version": EXPECTED_FAP_VERSION,
        "epm_engine_version": EXPECTED_EPM_VERSION,
        "git_commit": sha,
        "git_branch": EXPECTED_BRANCH,
        "git_repo_slug": EXPECTED_REPO_SLUG,
        "fap_core_connected": True,
        "environment": EXPECTED_ENVIRONMENT,
        "fap_core_service": EXPECTED_FAP_CORE_SERVICE,
        "fap_core_git_commit": "5" * 40,
        "fap_core_git_repo_slug": EXPECTED_FAP_CORE_REPO,
    }
    client = FakeClient([FakeResponse(payload)])
    ticks = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr("ops.render_release.time.monotonic", lambda: next(ticks))

    with pytest.raises(RuntimeError, match="fap_core_commit"):
        verify_runtime_health(
            "https://example.test/health",
            sha,
            wanted_core,
            timeout_seconds=1,
            interval_seconds=0,
            client=client,
            sleep=lambda _: None,
        )
