"""Fail-closed production release controller for FAP-Insurance on Render.

The controller deploys one exact Git SHA, verifies Render reports that same SHA,
verifies the live runtime self-identifies as that SHA, writes an attestation, and
rolls back to the previously live deploy if the release cannot be proven.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

API_BASE = "https://api.render.com/v1"
DEFAULT_SERVICE_ID = "srv-d9fp2l3bc2fs73blamug"
DEFAULT_HEALTH_URL = "https://fap-core.onrender.com/health"
DEFAULT_FAP_CORE_IDENTITY_URL = "https://fap-core-odm4.onrender.com/auth/check"
LEGACY_HEALTH_CHECK_PATH = "/health"
EXPECTED_HEALTH_CHECK_PATH = "/live"
EXPECTED_REPO_SLUG = "paslaycorp/FAP-Insurance"
EXPECTED_BRANCH = "main"
EXPECTED_FAP_VERSION = "0.3.0-grand-slam"
EXPECTED_EPM_VERSION = "epm-engine/0.1.2"
EXPECTED_ENVIRONMENT = "production"
EXPECTED_FAP_CORE_SERVICE = "fap-core"
EXPECTED_FAP_CORE_REPO = "paslaycorp/FAP-Core-v0.2.0"
EXPECTED_FAP_CORE_ENVIRONMENT = "production"
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
TERMINAL_FAILURES = {
    "build_failed",
    "canceled",
    "cancelled",
    "deactivated",
    "pre_deploy_failed",
    "update_failed",
}
EPM_PIN_RE = re.compile(
    r"EPM---EVIDENTIARY-PROVENANCE-MODEL-\.git@(?P<sha>[0-9a-f]{40})"
)


@dataclass
class ReleaseAttestation:
    schema_version: str
    release_sha: str
    epm_pin_sha: str
    expected_fap_core_sha: str
    previous_live_deploy_id: str | None
    previous_live_sha: str | None
    render_deploy_id: str | None
    render_deploy_sha: str | None
    render_status: str | None
    render_health_check_path: str | None
    runtime_health: dict[str, Any] | None
    dependency_preflight: dict[str, Any] | None
    workflow_url: str | None
    verified_at: str
    result: str
    rollback_deploy_id: str | None = None
    rollback_status: str | None = None
    rollback_runtime_health: dict[str, Any] | None = None
    failure: str | None = None


class RenderAPI:
    def __init__(
        self,
        token: str,
        service_id: str,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.service_id = service_id
        self.client = client or httpx.Client(
            base_url=API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _request(self, method: str, path: str, **kwargs) -> Any:
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else None

    def get_service(self) -> dict[str, Any]:
        return self._request("GET", f"/services/{self.service_id}")

    def disable_autodeploy(self) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/services/{self.service_id}",
            json={"autoDeploy": "no"},
        )

    def set_health_check_path(self, path: str) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/services/{self.service_id}",
            json={"serviceDetails": {"healthCheckPath": path}},
        )

    @staticmethod
    def _unwrap_deploy(item: dict[str, Any]) -> dict[str, Any]:
        deploy = item.get("deploy")
        return deploy if isinstance(deploy, dict) else item

    def list_deploys(self, limit: int = 20) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            f"/services/{self.service_id}/deploys",
            params={"limit": limit},
        )
        if not isinstance(payload, list):
            raise TypeError("Render deploy list returned a non-list payload")
        return [self._unwrap_deploy(item) for item in payload]

    def current_live_deploy(self) -> dict[str, Any] | None:
        for deploy in self.list_deploys():
            if deploy.get("status") == "live":
                return deploy
        return None

    def trigger_deploy(self, commit_sha: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/services/{self.service_id}/deploys",
            json={"commitId": commit_sha},
        )

    def get_deploy(self, deploy_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/services/{self.service_id}/deploys/{deploy_id}",
        )

    def rollback(self, deploy_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/services/{self.service_id}/rollback",
            json={"deployId": deploy_id},
        )


def deploy_commit_sha(deploy: dict[str, Any] | None) -> str | None:
    if not deploy:
        return None
    commit = deploy.get("commit") or {}
    return commit.get("id")


def wait_for_live(
    api: RenderAPI,
    deploy_id: str,
    *,
    timeout_seconds: int = 900,
    interval_seconds: int = 10,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        deploy = api.get_deploy(deploy_id)
        status = str(deploy.get("status", "unknown"))
        if status == "live":
            return deploy
        if status in TERMINAL_FAILURES or status.endswith("_failed"):
            raise RuntimeError(f"Render deploy {deploy_id} failed with status {status}")
        sleep(interval_seconds)
    raise TimeoutError(f"Render deploy {deploy_id} did not become live before timeout")


def read_epm_pin(path: str | Path = "requirements.txt") -> str:
    match = EPM_PIN_RE.search(Path(path).read_text(encoding="utf-8"))
    if not match:
        raise RuntimeError("Could not prove the pinned EPM release SHA from requirements.txt")
    return match.group("sha")


def verify_dependency_preflight(
    identity_url: str,
    expected_sha: str,
    api_key: str,
    *,
    max_attempts: int = 3,
    required_successes: int = 2,
    interval_seconds: int = 15,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Require bounded, repeatable FAP-Core readiness before production mutation."""
    http = client or httpx.Client(timeout=20.0)
    observations: list[dict[str, Any]] = []
    consecutive = 0

    for attempt in range(1, max_attempts + 1):
        observation: dict[str, Any] = {"attempt": attempt}
        try:
            response = http.get(
                identity_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Cache-Control": "no-cache",
                },
            )
            observation["status_code"] = response.status_code
            if response.status_code == 200:
                data = response.json()
                observation["payload"] = data
                checks = {
                    "status": isinstance(data, dict) and data.get("status") == "healthy",
                    "service": isinstance(data, dict) and data.get("service") == EXPECTED_FAP_CORE_SERVICE,
                    "commit": isinstance(data, dict) and data.get("git_commit") == expected_sha,
                    "repo": isinstance(data, dict) and data.get("git_repo_slug") == EXPECTED_FAP_CORE_REPO,
                    "environment": isinstance(data, dict) and data.get("environment") == EXPECTED_FAP_CORE_ENVIRONMENT,
                }
                healthy = all(checks.values())
                observation["checks"] = checks
                observation["healthy"] = healthy
                consecutive = consecutive + 1 if healthy else 0
            else:
                observation["healthy"] = False
                consecutive = 0
        except Exception as exc:  # noqa: BLE001 - preserve diagnostic boundary
            observation["healthy"] = False
            observation["error"] = str(exc)
            consecutive = 0

        observations.append(observation)
        if consecutive >= required_successes:
            return {
                "verified": True,
                "required_successes": required_successes,
                "observations": observations,
            }
        if attempt < max_attempts:
            sleep(interval_seconds)

    raise RuntimeError(
        "FAP-Core dependency preflight failed before deployment; "
        f"observations={observations}"
    )


def verify_runtime_health(
    health_url: str,
    release_sha: str,
    expected_fap_core_sha: str,
    *,
    timeout_seconds: int = 300,
    interval_seconds: int = 10,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    http = client or httpx.Client(timeout=20.0)
    deadline = time.monotonic() + timeout_seconds
    last_problem = "no response"

    while time.monotonic() < deadline:
        try:
            response = http.get(health_url, headers={"Cache-Control": "no-cache"})
            response.raise_for_status()
            data = response.json()
            checks = {
                "status": data.get("status") == "healthy",
                "service": data.get("service") == "fap-insurance",
                "version": data.get("version") == EXPECTED_FAP_VERSION,
                "epm": data.get("epm_engine_version") == EXPECTED_EPM_VERSION,
                "commit": data.get("git_commit") == release_sha,
                "branch": data.get("git_branch") == EXPECTED_BRANCH,
                "repo": data.get("git_repo_slug") == EXPECTED_REPO_SLUG,
                "fap_core": data.get("fap_core_connected") is True,
                "environment": data.get("environment") == EXPECTED_ENVIRONMENT,
                "fap_core_service": data.get("fap_core_service") == EXPECTED_FAP_CORE_SERVICE,
                "fap_core_commit": data.get("fap_core_git_commit") == expected_fap_core_sha,
                "fap_core_repo": data.get("fap_core_git_repo_slug") == EXPECTED_FAP_CORE_REPO,
            }
            if all(checks.values()):
                return data
            failed = [name for name, ok in checks.items() if not ok]
            last_problem = f"health proof mismatch: {', '.join(failed)}; payload={data}"
        except Exception as exc:  # noqa: BLE001 - retries intentionally cover transport/startup
            last_problem = str(exc)
        sleep(interval_seconds)

    raise RuntimeError(f"Runtime health could not prove release {release_sha}: {last_problem}")


def verify_rollback_health(
    health_url: str,
    expected_sha: str,
    *,
    timeout_seconds: int = 120,
    interval_seconds: int = 10,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Prove the rolled-back runtime is the prior SHA and dependency-ready."""
    http = client or httpx.Client(timeout=20.0)
    deadline = time.monotonic() + timeout_seconds
    last_problem = "no response"

    while time.monotonic() < deadline:
        try:
            response = http.get(health_url, headers={"Cache-Control": "no-cache"})
            response.raise_for_status()
            data = response.json()
            checks = {
                "status": data.get("status") == "healthy",
                "service": data.get("service") == "fap-insurance",
                "commit": data.get("git_commit") == expected_sha,
                "branch": data.get("git_branch") == EXPECTED_BRANCH,
                "repo": data.get("git_repo_slug") == EXPECTED_REPO_SLUG,
                "fap_core": data.get("fap_core_connected") is True,
            }
            if all(checks.values()):
                return data
            failed = [name for name, ok in checks.items() if not ok]
            last_problem = f"rollback health mismatch: {', '.join(failed)}; payload={data}"
        except Exception as exc:  # noqa: BLE001 - bounded retry for rollback proof
            last_problem = str(exc)
        sleep(interval_seconds)

    raise RuntimeError(
        f"Rollback runtime could not prove prior release {expected_sha}: {last_problem}"
    )


def workflow_url() -> str | None:
    server = os.getenv("GITHUB_SERVER_URL")
    repo = os.getenv("GITHUB_REPOSITORY")
    run_id = os.getenv("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


def write_attestation(attestation: ReleaseAttestation, path: str = "release-attestation.json") -> None:
    payload = json.dumps(asdict(attestation), indent=2, sort_keys=True) + "\n"
    Path(path).write_text(payload, encoding="utf-8")
    print(payload)

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write("## Production release attestation\n\n")
            handle.write(f"- Result: **{attestation.result}**\n")
            handle.write(f"- Git SHA: `{attestation.release_sha}`\n")
            handle.write(f"- EPM pin: `{attestation.epm_pin_sha}`\n")
            handle.write(f"- Expected FAP-Core SHA: `{attestation.expected_fap_core_sha}`\n")
            handle.write(f"- Render deploy: `{attestation.render_deploy_id}`\n")
            handle.write(f"- Render status: `{attestation.render_status}`\n")
            handle.write(
                f"- Render health check: `{attestation.render_health_check_path}`\n"
            )
            if attestation.failure:
                handle.write(f"- Failure: `{attestation.failure}`\n")
            if attestation.rollback_deploy_id:
                handle.write(f"- Rollback deploy: `{attestation.rollback_deploy_id}`\n")


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def release() -> ReleaseAttestation:
    token = require_env("RENDER_API_KEY")
    release_sha = require_env("RELEASE_SHA")
    service_id = os.getenv("RENDER_SERVICE_ID", DEFAULT_SERVICE_ID)
    health_url = os.getenv("PRODUCTION_HEALTH_URL", DEFAULT_HEALTH_URL)
    fap_core_identity_url = os.getenv(
        "FAP_CORE_IDENTITY_URL",
        DEFAULT_FAP_CORE_IDENTITY_URL,
    )
    fap_core_api_key = require_env("FAP_CORE_API_KEY")
    expected_fap_core_sha = require_env("EXPECTED_FAP_CORE_SHA")
    if not _SHA40_RE.fullmatch(expected_fap_core_sha):
        raise RuntimeError("EXPECTED_FAP_CORE_SHA must be an exact 40-character lowercase SHA")
    epm_pin = read_epm_pin()
    api = RenderAPI(token, service_id)

    previous = api.current_live_deploy()
    previous_id = previous.get("id") if previous else None
    previous_sha = deploy_commit_sha(previous)
    deploy_id: str | None = None
    rollback_id: str | None = None
    rollback_status: str | None = None
    original_health_path: str | None = None
    health_path_restore_error: str | None = None

    attestation = ReleaseAttestation(
        schema_version="fap.production-release-attestation/1.2",
        release_sha=release_sha,
        epm_pin_sha=epm_pin,
        expected_fap_core_sha=expected_fap_core_sha,
        previous_live_deploy_id=previous_id,
        previous_live_sha=previous_sha,
        render_deploy_id=None,
        render_deploy_sha=None,
        render_status=None,
        render_health_check_path=None,
        runtime_health=None,
        dependency_preflight=None,
        workflow_url=workflow_url(),
        verified_at=datetime.now(timezone.utc).isoformat(),
        result="started",
    )

    try:
        service = api.get_service()
        if service.get("branch") != EXPECTED_BRANCH:
            raise RuntimeError(
                f"Render service branch is {service.get('branch')!r}, expected {EXPECTED_BRANCH!r}"
            )
        repo = str(service.get("repo", ""))
        if not repo.endswith("/paslaycorp/FAP-Insurance"):
            raise RuntimeError(f"Unexpected Render repository binding: {repo!r}")

        # Prove the canonical downstream dependency before mutating production.
        attestation.dependency_preflight = verify_dependency_preflight(
            fap_core_identity_url,
            expected_fap_core_sha,
            fap_core_api_key,
        )

        service_details = service.get("serviceDetails") or {}
        original_health_path = service_details.get("healthCheckPath")
        if original_health_path not in {
            LEGACY_HEALTH_CHECK_PATH,
            EXPECTED_HEALTH_CHECK_PATH,
        }:
            raise RuntimeError(
                "Unexpected Render health check path before release: "
                f"{original_health_path!r}"
            )

        # GitHub Actions becomes the sole deployment authority. This removes the
        # broken and unaudited provider webhook from the production trust path.
        api.disable_autodeploy()

        created = api.trigger_deploy(release_sha)
        deploy_id = created.get("id")
        if not deploy_id:
            raise RuntimeError(f"Render did not return a deploy id: {created}")
        attestation.render_deploy_id = deploy_id

        created_sha = deploy_commit_sha(created)
        if created_sha and created_sha != release_sha:
            raise RuntimeError(
                f"Render created deploy for {created_sha}, expected {release_sha}"
            )

        live = wait_for_live(api, deploy_id)
        live_sha = deploy_commit_sha(live)
        attestation.render_deploy_sha = live_sha
        attestation.render_status = live.get("status")
        if live_sha != release_sha:
            raise RuntimeError(
                f"Live Render deploy reports {live_sha}, expected {release_sha}"
            )

        attestation.runtime_health = verify_runtime_health(
            health_url,
            release_sha,
            expected_fap_core_sha,
        )

        # Migrate Render's platform liveness probe only after the new runtime has
        # proved its exact identity and dependency readiness. This avoids pointing
        # the previous runtime at an endpoint it does not yet implement.
        service = api.set_health_check_path(EXPECTED_HEALTH_CHECK_PATH)
        configured_health_path = (service.get("serviceDetails") or {}).get(
            "healthCheckPath"
        )
        if configured_health_path != EXPECTED_HEALTH_CHECK_PATH:
            raise RuntimeError(
                "Render health check path was not established as "
                f"{EXPECTED_HEALTH_CHECK_PATH!r}: {configured_health_path!r}"
            )
        attestation.render_health_check_path = configured_health_path

        attestation.result = "verified"
        attestation.verified_at = datetime.now(timezone.utc).isoformat()
        write_attestation(attestation)
        return attestation

    except Exception as exc:
        attestation.failure = str(exc)
        attestation.result = "failed"
        attestation.verified_at = datetime.now(timezone.utc).isoformat()

        # If this release attempted the liveness-path migration and then failed,
        # restore the prior provider configuration before/with rollback.
        if (
            original_health_path
            and original_health_path != EXPECTED_HEALTH_CHECK_PATH
        ):
            try:
                api.set_health_check_path(original_health_path)
            except Exception as health_path_exc:  # noqa: BLE001
                health_path_restore_error = str(health_path_exc)

        if deploy_id and previous_id and previous_sha and previous_sha != release_sha:
            try:
                rolled = api.rollback(previous_id)
                rollback_id = rolled.get("id")
                if rollback_id:
                    rollback_live = wait_for_live(api, rollback_id)
                    rollback_status = str(rollback_live.get("status"))
                    try:
                        attestation.rollback_runtime_health = verify_rollback_health(
                            health_url,
                            previous_sha,
                        )
                    except Exception as rollback_health_exc:  # noqa: BLE001
                        rollback_status = (
                            f"{rollback_status}; health-unproven: {rollback_health_exc}"
                        )
                else:
                    rollback_status = "rollback-requested"
            except Exception as rollback_exc:  # noqa: BLE001 - preserve both failures
                rollback_status = f"rollback-failed: {rollback_exc}"

        if health_path_restore_error:
            rollback_status = (
                f"{rollback_status or 'unknown'}; "
                f"health-path-restore-failed: {health_path_restore_error}"
            )

        attestation.rollback_deploy_id = rollback_id
        attestation.rollback_status = rollback_status
        write_attestation(attestation)
        raise


def main() -> int:
    try:
        release()
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"PRODUCTION RELEASE FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
