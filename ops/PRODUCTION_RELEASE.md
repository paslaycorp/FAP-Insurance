# FAP-Insurance Production Release Boundary

## Authority

GitHub Actions is the production deployment authority for FAP-Insurance.

Render provider state is not source authority. Provider-driven auto-deploy is outside the accepted release path. The release controller disables Render auto-deploy before controlled exact-SHA deployment.

## Release trigger

Production release is **manual exact-SHA dispatch** through `.github/workflows/release-production.yml`.

A merge to `main` runs validation but does not itself authorize or dispatch production. The operator supplies both the full 40-character current FAP-Insurance merge SHA and the full 40-character already-live FAP-Core runtime SHA to the Production Release workflow.

Manual dispatch does not bypass CI, merge provenance, current-main freshness, merge topology, runtime proof, or rollback controls.

## Required provenance chain

A production release is accepted only when all of these statements are proven:

1. The candidate is the current `main` commit and has not been superseded.
2. The candidate is a two-parent merge commit.
3. The candidate is uniquely attributable to a merged PR into `main`.
4. Required FAP-Insurance CI/verification checks completed successfully for that exact SHA.
5. `requirements.txt` contains a recoverable exact EPM commit pin.
6. Render creates a deployment for the exact candidate SHA.
7. That exact Render deployment reaches provider `live`.
8. Before production mutation, FAP-Core `/health` identifies the exact operator-supplied Core SHA, expected repository/service, and production posture.
9. Runtime `/health` identifies the same FAP-Insurance Git SHA, branch, repository, expected FAP/EPM versions, production posture, and authenticated FAP-Core identity matching the exact supplied Core SHA.
10. A machine-readable release attestation is emitted and retained.

A Render `live` status alone is not release proof.

## Required credentials and runtime configuration

Release control requires:

- `RENDER_API_KEY` in the protected GitHub `production` environment.

Application runtime requires, at minimum:

- `FAP_API_KEY`;
- `FAP_CORE_URL`;
- `FAP_CORE_API_KEY`.

The FAP-Core service credential is required for authenticated `/verify` and runtime-identity observation. Missing credential must fail closed; it must not be replaced by unauthenticated health as trust evidence.

Never place secret values in source, workflow YAML, issues, logs, chat, or release evidence.

## Fail-closed behavior

The workflow refuses or fails release acceptance when:

- required CI did not succeed for the target SHA;
- the candidate is no longer current `main`;
- merge topology/provenance is invalid;
- `RENDER_API_KEY` is unavailable;
- Render service source identity is wrong;
- Render deploys a different commit;
- deployment reaches a terminal failure state;
- runtime identity does not match the exact release SHA and expected versions;
- required FAP-Core connectivity is not established.

If failure occurs after production mutation begins and a prior live deployment exists, the controller requests rollback and records the outcome.

## Production identifiers

- Render service: `srv-d9fp2l3bc2fs73blamug`
- Production URL: `https://fap-core.onrender.com`
- Health proof URL: `https://fap-core.onrender.com/health`
- Production branch: `main`
- Repository: `paslaycorp/FAP-Insurance`

## Operator path

`merged PR → current main merge SHA → required checks green → manual Production Release dispatch with exact SHA → Render deployment → runtime proof → attestation`

## Attestation

Successful and failed release attempts write `release-attestation.json` when the controller runs. The workflow retains it as an Actions artifact.

The attestation records at minimum:

- target Git SHA;
- pinned EPM SHA;
- exact expected FAP-Core SHA;
- dependency preflight identity observations;
- previously live Render deployment/SHA;
- new Render deployment ID/SHA/status;
- runtime health identity;
- GitHub workflow URL;
- verification timestamp;
- rollback ID/status when applicable;
- failure reason when applicable.

## Acceptance criterion

The production deployment boundary is closed only when the exact current-main merge commit completes the controlled chain and the resulting attestation proves runtime identity equals the reviewed/tested GitHub identity. No merge, provider status, or manual observation may substitute for that evidence.
