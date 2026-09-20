from pathlib import Path

RELEASE = Path(".github/workflows/release-production.yml")
CI = Path(".github/workflows/ci.yml")
VERIFY = Path(".github/workflows/verify.yml")


def test_production_release_requires_explicit_manual_dispatch():
    text = RELEASE.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "workflow_run:" not in text
    assert 'required: true' in text
    assert 'description: "Exact merged main-branch commit SHA to release"' in text


def test_ci_never_repairs_the_candidate_under_test():
    text = CI.read_text(encoding="utf-8")

    assert "ruff check --fix" not in text


def test_github_hosted_runner_family_is_fixed():
    for path in (RELEASE, CI, VERIFY):
        text = path.read_text(encoding="utf-8")
        assert "runs-on: ubuntu-latest" not in text
        assert "runs-on: ubuntu-24.04" in text


def test_release_actions_remain_immutable():
    text = RELEASE.read_text(encoding="utf-8")

    assert "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803" in text
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in text
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in text

def test_ci_and_verification_toolchains_are_exact():
    ci = CI.read_text(encoding="utf-8")
    verify = VERIFY.read_text(encoding="utf-8")
    release = RELEASE.read_text(encoding="utf-8")

    assert 'python-version: "3.12.14"' in ci
    assert 'python-version: "3.13.15"' in verify
    assert '"pip==26.2.1"' in ci
    assert '"ruff==0.16.8"' in ci
    assert '"pip==26.2.1"' in verify
    assert 'python-version: "3.12.14"' in release
    assert '"pip==26.2.1"' in release


def test_release_requires_merge_commit_topology():
    text = RELEASE.read_text(encoding="utf-8")

    assert "Require merge-commit topology" in text
    assert 'if [[ "${#parts[@]}" -ne 3 ]]' in text


def test_release_binds_exact_fap_core_sha():
    text = RELEASE.read_text(encoding="utf-8")

    assert "fap_core_sha:" in text
    assert 'description: "Exact already-live FAP-Core commit SHA required by this release"' in text
    assert "EXPECTED_FAP_CORE_SHA:" in text


def test_release_permissions_are_least_privilege():
    text = RELEASE.read_text(encoding="utf-8")

    assert "contents: read" in text
    assert "actions: read" in text
    assert "pull-requests: read" in text
    assert "deployments: write" not in text
