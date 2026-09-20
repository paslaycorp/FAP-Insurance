# FAP-Insurance Service Objectives

## Status

These objectives separate **hard assurance invariants** from **service-level targets**. Hard invariants are acceptance conditions. Availability/latency targets are provisional until production telemetry establishes a baseline; this document does not claim historical uptime.

## Hard invariants

The error budget for these conditions is zero:

1. An accepted production release must identify the exact reviewed current-main merge SHA at runtime.
2. A production candidate must have successful required checks for the exact candidate SHA.
3. A FAP verdict, score, confidence, or raw trust boolean must never independently create EPM authority.
4. A receipt producer SHA must match the independently observed authenticated FAP-Core runtime SHA before it can establish the trusted source boundary.
5. Missing, stale, contradictory, malformed, wrong-contract, or wrong-runtime receipts must not authorize.
6. Material context changes must not inherit authorization merely because the source receipt was valid.
7. A failed runtime release proof must remain a failed release and produce evidence of failure/rollback where applicable.

Any violation of an invariant is an incident, not allowable error-budget consumption.

## Operational targets

Until at least 30 days of representative production telemetry is retained, treat numeric availability and latency thresholds as proposed targets rather than achieved SLOs.

Initial targets for measurement:

- process liveness availability: target ≥ 99.9% monthly;
- authenticated dependency readiness: measure separately from process liveness;
- verification request success/blocked/error rates: report separately so fail-closed decisions are not mislabeled outages;
- p95 verification latency: establish baseline before committing a contractual threshold;
- release verification: 100% of accepted releases retain machine-readable attestation.

## Required measurements

Track at minimum:

- `/live` success rate;
- `/health` FAP-Core connectivity state;
- EPM decision counts by AUTHORIZED, AUTHORIZED_WITH_CONSTRAINTS, DEFER, QUARANTINE, DENY;
- source-degradation counts;
- receipt validation rejection categories;
- request latency;
- release success/failure/rollback counts;
- runtime SHA versus release SHA;
- audit-chain integrity status.

## Interpretation rules

- `DEFER`, `QUARANTINE`, or `DENY` caused by evidence/authority constraints are not automatically availability failures.
- `/live` success does not imply dependency readiness.
- provider `live` state does not imply release acceptance.
- a successful unit/CI test run does not count as production availability evidence.

## Review cadence

After 30 days of representative production telemetry:

1. calculate actual availability and latency distributions;
2. define a defensible p95 latency SLO;
3. set a dependency-readiness target separately from liveness;
4. establish an availability error budget;
5. retain the zero-error-budget assurance invariants unchanged unless the architecture contract itself changes.
