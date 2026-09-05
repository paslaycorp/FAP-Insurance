# EPM Assurance Exchange v0.1

**Status:** Architecture specification / implementation deferred
**Issue:** #3

## Purpose

Establish a reciprocal machine-verifiable attestation boundary between EPM and trusted verification engines such as FAP-Core. The exchange proves provenance and integrity of a verification assertion; it does not establish truth.

## Mature communication path

```text
Internet
  ↓ TLS / edge
EPM
  │ authenticated service identity (mTLS preferred)
  │ request digest + nonce + evidence/context binding
  ↓
FAP-Core / trusted verification engine
  │ executes verification
  │ binds result to request/evidence
  │ signs response attestation
  ↓
EPM
  │ verifies identity, signature, replay, digests, evidence,
  │ freshness, engine/policy/oracle versions
  ↓
EPM assurance evaluation
  ↓
Governor
  ↓
Decision + immutable audit
```

Transport identity and application attestation are separate controls and should both exist in the mature design.

## Request contract

Minimum fields:

- `protocol_version`
- `request_id`
- `nonce`
- `request_digest`
- `evidence_id`
- `media_hash`
- `timestamp_claimed`
- `purpose`
- `scope`
- `jurisdiction`
- `consequence`
- `requested_operation`
- `created_at`
- `expires_at`

Digest calculation must use a deterministic canonical representation.

## Response attestation

Minimum fields:

- `protocol_version`
- `request_id`
- `nonce`
- `request_digest`
- `response_digest`
- `evidence_id`
- `media_hash`
- `artifact_id`
- `result`
- `confidence`
- `engine_id`
- `engine_version`
- `policy_id`
- `policy_version`
- `oracle_versions`
- `processed_at`
- `valid_until`
- `attestation_status`
- `signature`
- `key_id`

## Verification order

1. Authenticate service identity.
2. Check protocol compatibility.
3. Verify signature and key status.
4. Check nonce/replay state.
5. Recompute and compare request digest.
6. Verify evidence ID and media hash.
7. Verify response digest.
8. Check freshness and temporal applicability.
9. Authorize engine identity/version.
10. Check policy identity/version compatibility.
11. Validate oracle provenance and degradation state.
12. Feed the attestation into EPM assurance evaluation.
13. Apply the Governor.

No earlier failure may be converted into a later success state.

## Replay and freshness

Replay state is scoped to service identity and nonce and persists for the validity window. Reuse of an identical response is still a replay; reuse with a changed response is replay plus a potential substitution attack.

`processed_at` describes verification execution time. It does not replace the evidence capture timestamp or oracle observation times. Freshness must therefore be policy-defined and consequence-sensitive.

## Failure taxonomy

`UNAUTHENTICATED_PEER`, `INVALID_SIGNATURE`, `REPLAY_DETECTED`, `REQUEST_BINDING_MISMATCH`, `EVIDENCE_BINDING_MISMATCH`, `RESPONSE_INTEGRITY_FAILURE`, `STALE_ATTESTATION`, `ENGINE_NOT_AUTHORIZED`, `POLICY_MISMATCH`, `ORACLE_PROVENANCE_UNRESOLVED`, `ATTESTATION_DEGRADED`, `ATTESTATION_UNAVAILABLE`.

These remain distinguishable in audit records even when an API maps several to one HTTP status.

## Audit binding

Bind request/response digests, service identity, engine/policy/oracle versions, attestation status, processing time, and signature key ID into the immutable audit record and existing hash chain.

## Threat coverage

| Threat | Control |
|---|---|
| Response substitution | Request/response digests |
| Replay | Nonce + persistent replay state + validity window |
| Cross-claim attachment | Evidence ID + media hash |
| Wrong service | mTLS/service identity + engine authorization |
| Wrong software | Engine version binding |
| Wrong policy | Policy ID/version |
| Oracle substitution | Oracle provenance/version binding |
| Payload alteration | Signature + response digest |
| Confused deputy | Requested operation + context |
| Stale result | Freshness / `valid_until` |

## Implementation phases

A. Contract and canonicalization only.

B. Test-only local loopback with deterministic keys; prove replay, substitution, wrong evidence, wrong policy, and stale-result failures.

C. mTLS/service identity and key rotation.

D. C2PA provenance adapter.

E. Control-assurance registry for SOC 3 and related organizational evidence.

F. Production deployment with persistent replay state, clock policy, observability, incident response, and recovery.

## Non-goals

C2PA is not the decision engine. SOC 3 is not a runtime wire protocol or truth token. A valid upstream attestation cannot bypass EPM applicability, integrity, provenance, authority, jurisdiction, temporal, consequence, or Governor controls.

## Acceptance criterion

An auditor must be able to reconstruct **which service produced which result for which exact evidence, in response to which exact request, under which engine/policy/oracle versions, at what time, with what freshness, and whether EPM authorized that result for the requested use.**
