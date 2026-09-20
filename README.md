# FAP-Insurance

**Insurance-domain evidence verification service with EPM assurance enforcement**

FAP-Insurance combines domain evidence processing with explicit EPM boundary checks. It consumes FAP-Core as an evidence-producing dependency while keeping provenance, epistemic status, applicability, and authorization semantics distinct.

## Production posture

The production path is designed around:

- merged-PR provenance;
- exact-SHA deployment;
- required CI and Production Verification checks;
- fail-closed dependency handling;
- runtime identity verification;
- rollback evidence;
- protected `main` as production authority.

The repository ruleset for `main` blocks deletion and non-fast-forward updates, requires pull requests, requires current status checks, and exposes no routine bypass actors.

## EPM boundary

Production consumes the EPM v0.1.2 runtime line.

EPM is not used as a confidence-score wrapper. The integration preserves distinctions including:

```text
evidence result != EPM authority
provenance != truth
healthy dependency != authorized decision
later receipt != earlier availability
valid transition != unrestricted downstream use
```

## FAP-Core dependency

FAP-Core remains a separate evidence-producing service. FAP-Insurance verifies dependency readiness and fails closed when the required connection cannot be established.

Platform liveness and dependency readiness are intentionally separated so infrastructure health polling does not silently redefine evidence readiness.

## Evidence and assurance flow

At a high level:

```text
request
  ↓
authenticated evidence receipt / availability boundary
  ↓
domain evidence collection and FAP-Core verification
  ↓
EPM context + temporal / authority / applicability checks
  ↓
bounded domain response + audit evidence
```

The service does not treat an upstream score, confidence value, or verdict as automatic authorization.

## Repository architecture

Key areas include:

- EPM state, constraints, temporal, source, resolution, and justification modules;
- FAP adapter and dependency-availability handling;
- audit and observability surfaces;
- domain evidence fusion and report generation;
- production verification and release workflows;
- adversarial and conformance tests.

Some legacy `dpie_*` module names remain for compatibility/history. Public architecture naming is EPM; renaming runtime modules should be handled as an explicit compatibility migration rather than a cosmetic mass rename.

## Current contract work

The EPM ↔ FAP Assurance Contract is versioned independently from production runtime changes. Contract work must not absorb insurance-domain behavior into the EPM kernel or transfer EPM decision authority into FAP-Core.

## Security and operations

Do not commit production credentials. Production releases should remain tied to exact source identity and machine-readable evidence. A failed runtime proof must remain a failed release rather than being normalized into success.
