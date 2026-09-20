# FAP-Insurance Threat Model

## Scope

This model covers the production authority chain from authenticated FAP-Insurance ingress through FAP-Core evidence production, FAP-Insurance boundary validation, EPM transition evaluation, release control, and audit evidence.

It does not claim to establish application security beyond the controls documented here.

## Protected assets

- exact source and runtime identity;
- canonical FAP evidence receipts;
- provenance references and evidence IDs;
- EPM context, state, and decisions;
- production credentials;
- audit records and release attestations;
- protected `main` as source authority.

## Trust boundaries

1. External caller → FAP-Insurance authenticated ingress.
2. FAP-Insurance → authenticated FAP-Core `/verify`.
3. FAP-Core producer receipt → FAP-Insurance trusted boundary validator.
4. Trusted boundary → EPM source-state evaluation.
5. GitHub protected `main` → production release workflow.
6. Release controller → Render runtime.
7. Runtime → retained machine-readable evidence.

## Primary threats and controls

### Verdict-to-authority smuggling

Threat: a FAP verdict, score, or confidence is treated as EPM `PRESERVED` or authorization.

Control: raw FAP observations start unresolved; only a validated trusted boundary may establish the bound source context.

### Self-asserted boundary trust

Threat: producer or caller sends `boundary_validated=true` or a typed preservation object and gains authority.

Control: raw mappings cannot grant boundary validation; caller-created boundary-validated preservation proofs are rejected at the raw compatibility boundary; FAP-Core producer-side boundary validation must be false.

### Receipt substitution or tampering

Threat: receipt evidence ID, provenance, contract revision, timestamp, schema, or receipt ID is altered.

Control: exact schema checks, evidence/provenance binding, contract revision binding, receipt-ID integrity calculation, chronology limits, and stale/future rejection.

### Runtime identity substitution

Threat: a valid-looking receipt names a producer SHA different from the service actually answering requests.

Control: authenticated FAP-Core runtime identity is independently observed and must match the receipt producer repository and exact commit SHA.

### Temporal backdating

Threat: evidence observed later is used as though available earlier.

Control: local availability, receipt chronology, maximum skew, maximum receipt age, and EPM temporal evaluation remain distinct and fail closed when incompatible.

### Context laundering

Threat: evidence valid for claim verification is reused for a materially different purpose, scope, jurisdiction, or rule.

Control: `ValidatedFAPBoundary` establishes only the exact bound source context; material transitions remain subject to EPM preservation/applicability evaluation.

### Release-source substitution

Threat: production runs a commit other than the reviewed current-main merge commit.

Control: protected main, required checks, exact-SHA manual release, merged-PR provenance, two-parent merge topology, runtime SHA proof, and attestation.

### Provider auto-deploy bypass

Threat: Render deploys repository changes outside the trusted release controller.

Control: provider auto-deploy is outside the accepted authority path and is disabled by the release controller before controlled deployment. Runtime identity/attestation remains required even if provider state reports live.

### Credential loss or misuse

Threat: missing or compromised service credentials break trust or permit unauthorized calls.

Control: secrets are external to source; missing FAP-Core service credential fails closed; production release credential is expected in the protected GitHub production environment.

## Residual risks

- compromise of GitHub, Render, or authorized credentials can undermine controls at their respective trust roots;
- authenticated runtime identity is only as trustworthy as the endpoint, transport, credential, and deployment platform that produce it;
- in-memory/process-local caches can preserve recently observed state within their designed TTL;
- audit retention and external log retention are operational dependencies;
- availability targets require real production measurement and are not inferred from CI;
- the current trusted source context is deliberately narrow and must not be generalized without a contract change.

## Security invariant

No single upstream observation, score, boolean, health response, or provider status is sufficient to create end-to-end assurance.
