# FAP-Insurance Production Release Boundary

## Authority

GitHub Actions is the production deployment authority for FAP-Insurance.

Render's provider-driven auto-deploy is intentionally removed from the trusted release path. The production workflow disables Render auto-deploy through the Render API before deploying an exact Git commit SHA.

## Required provenance chain

A production release is accepted only when all of these statements are proven:

1. The candidate is the current `main` commit and has not been superseded.
2. `FAP-Insurance CI/CD` completed successfully for that exact SHA.
3. `requirements.txt` contains a recoverable exact EPM commit pin.
4. Render creates a deployment for the exact candidate SHA.
5. That exact Render deployment reaches `live`.
6. `/health` reports the same Git SHA at runtime.
7. `/health` reports branch `main`, repository `paslaycorp/FAP-Insurance`, the expected FAP version, the expected EPM engine version, and a connected FAP-Core.
8. A machine-readable release attestation is emitted and retained as a GitHub Actions artifact.

A Render `live` status alone is not release proof.

## Fail-closed behavior

The workflow refuses to deploy when:

- the CI workflow failed;
- a manual release cannot prove a successful CI run for the target SHA;
- the candidate is no longer the current `main` SHA;
- `RENDER_API_KEY` is unavailable;
- the Render service points at the wrong branch or repository;
- Render deploys a different commit;
- the deployment enters a terminal failure state;
- runtime health does not identify the exact release SHA and expected EPM/FAP versions.

If failure occurs after production mutation begins and a prior live deployment exists, the controller requests a Render rollback to that prior deployment and records the rollback outcome in the attestation.

## One-time credential requirement

Create a GitHub Actions secret named:

`RENDER_API_KEY`

Prefer storing it in the GitHub `production` environment rather than as a broadly available repository secret. The token must be authorized to read/update the FAP-Insurance Render service and create/retrieve/rollback deployments.

Never place the token in source, workflow YAML, issues, logs, chat, or Render environment variables used by the application.

## Production identifiers

- Render service: `srv-d9fp2l3bc2fs73blamug`
- Production URL: `https://fap-core.onrender.com`
- Health proof URL: `https://fap-core.onrender.com/health`
- Production branch: `main`
- Repository: `paslaycorp/FAP-Insurance`

## Workflow

`.github/workflows/release-production.yml`

Automatic path:

`main push -> FAP-Insurance CI/CD -> success -> Production Release -> exact-SHA Render deployment -> runtime proof -> attestation`

Manual dispatch exists only for recovery. It does not bypass CI: the requested SHA must already have a successful CI/CD workflow run and must still equal current `main`.

## Attestation

Successful and failed release attempts write `release-attestation.json` when the controller runs. The workflow uploads it as a 90-day Actions artifact.

The attestation records at minimum:

- target Git SHA;
- pinned EPM SHA;
- previously live Render deploy/SHA;
- new Render deploy ID/SHA/status;
- runtime health identity;
- GitHub workflow URL;
- verification timestamp;
- rollback ID/status when applicable;
- failure reason when applicable.

## Acceptance criterion

The production deployment boundary is closed only when a real `main` commit completes this chain without manual Render intervention and the resulting attestation proves that the runtime SHA equals the tested GitHub SHA.
