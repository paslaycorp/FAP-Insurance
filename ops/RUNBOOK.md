# FAP-Insurance Operations Runbook

## Rule zero

Repository state is not production state. A green pull request, a merge, or a Render `live` flag does not by itself prove which code is running or what assurance path authorized a decision. Treat a production release as accepted only when the exact-SHA release workflow emits evidence that binds GitHub source identity to runtime identity.

## Normal operating surfaces

- `GET /live`: process liveness only. It intentionally does not call FAP-Core.
- `GET /health`: service health plus FAP-Core authenticated runtime-identity reachability.
- `GET /epm/metrics`: authenticated EPM operational metrics.
- `POST /verify`: authenticated production verification path.

A healthy `/live` with an unhealthy dependency is an expected degraded state, not proof of end-to-end readiness.

## Required production dependencies

FAP-Insurance requires:

1. a receipt-capable FAP-Core runtime;
2. `FAP_CORE_URL` pointing to the intended FAP-Core service;
3. `FAP_CORE_API_KEY` configured in the FAP-Insurance runtime environment;
4. `FAP_API_KEY` for FAP-Insurance ingress;
5. the GitHub production environment `RENDER_API_KEY` for controlled releases;
6. the GitHub production environment `FAP_CORE_API_KEY` for authenticated pre-deploy Core identity proof.

Never copy secret values into issues, pull requests, workflow logs, documentation, chat, or release evidence.

## Pre-release checklist

Before any production release:

1. Candidate is the current protected `main` SHA.
2. Candidate is a two-parent merge commit attributable to one merged PR.
3. FAP-Insurance CI, Build, and Production Verification are green for the exact candidate.
4. FAP-Core is already running a receipt-capable build compatible with the pinned EPM-FAP contract revision.
5. The production runtime has `FAP_CORE_API_KEY` configured.
6. The release workflow has access to both `RENDER_API_KEY` and `FAP_CORE_API_KEY` through the protected production environment.
7. The GitHub-side `FAP_CORE_API_KEY` corresponds to the same Core service credential configured for FAP-Insurance runtime use.
8. No unresolved incident or authority-boundary exception exists.

## Release procedure

Production release is manual and exact-SHA.

1. Open GitHub Actions → **Production Release**.
2. Choose **Run workflow**.
3. Supply the full 40-character current FAP-Insurance `main` merge SHA.
4. Supply the full 40-character **already-live** FAP-Core runtime SHA observed after the Core release proof.
5. Do not substitute a branch name, tag, shortened SHA, or unverified dependency SHA.
6. Allow the release controller to prove the exact FAP-Core identity before production mutation and again through authenticated FAP-Insurance health after deployment.
7. Inspect the generated `release-attestation.json`.
8. Accept the release only if the attestation records `result=verified`, the exact target SHA, the exact expected FAP-Core SHA, matching runtime Git identities, expected EPM/FAP versions, and production runtime posture.

Do not manually edit the Render service to make a failed release appear healthy.

## Decision-boundary expectations

FAP-Core verdict, score, confidence, receipt booleans, or producer-side boundary claims do not create EPM authority.

A normal matching-context authorization path requires:

`authenticated local ingress → FAP-Core /verify → canonical evidence receipt → authenticated runtime identity → FAP-Insurance trusted validator → ValidatedFAPBoundary → EPM transition evaluation`

If the trusted validator cannot establish the boundary, the request must remain unresolved or fail closed according to the EPM result.

## Degraded-state guide

| Observation | Interpretation | Operator action |
| --- | --- | --- |
| `/live` fails | FAP-Insurance process unavailable | inspect deployment/runtime logs; do not diagnose as an EPM failure first |
| `/live` succeeds, `/health` reports FAP-Core disconnected | dependency or credential path unavailable | check FAP-Core runtime and credential presence; do not bypass trusted validation |
| valid request returns EPM `DEFER` | assurance basis not established | inspect receipt validation and runtime identity; do not map verdict to authorization |
| temporal mismatch / material context shift | evidence cannot support requested use under current context | preserve the decision and evidence; do not override by changing receipt fields |
| exact runtime SHA differs from release SHA | release integrity failure | treat release as failed and rollback |
| receipt producer SHA differs from observed FAP-Core SHA | trust-boundary failure | block authorization and investigate FAP-Core deployment/receipt source |

## Rollback

Rollback is a release-integrity operation, not a semantic override.

If a release mutates production but fails runtime proof, the release controller should request rollback to the previously live deployment and record the outcome in the release attestation.

After rollback:

1. prove the restored runtime SHA;
2. prove expected EPM/FAP versions;
3. confirm FAP-Core connectivity;
4. preserve the failed and rollback attestations;
5. open an incident record before another release attempt.

## Evidence preservation

For every production release or material incident retain:

- merged PR number and merge SHA;
- exact CI/verification run identifiers;
- Render deployment ID;
- runtime health identity;
- FAP-Core runtime identity when relevant;
- release attestation;
- rollback deployment ID/status when applicable;
- incident timeline and operator actions.

Do not reconstruct missing historical evidence and present it as original evidence.

## Stop conditions

Stop normal operation or release progression when any of these occur:

- runtime identity cannot be proven;
- receipt/runtime identity contradict;
- production secret availability is uncertain;
- current `main` changes after the candidate is selected;
- a release requires bypassing protected-main or fail-closed controls;
- an operator would need to assert assurance manually to proceed.
