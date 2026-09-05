# EPM Assurance Exchange v0.1

**Status:** Architecture specification / implementation deferred
**Issue:** #3
**Scope:** EPM ↔ trusted verification engines (for example, FAP-Core)

## 1. Purpose

EPM must be able to distinguish a verification result that merely arrived over a network from a verification result that can be attributed to a specific verification service, bound to the exact evidence and request, and checked for freshness and substitution.

The exchange therefore establishes a reciprocal, machine-verifiable attestation boundary.

The exchange does **not** establish truth. It establishes provenance and integrity of the verification service's assertion.

## 2. Security model

The mature communication path has two distinct layers:

1. **Authenticated transport:** mTLS or an equivalent service-identity mechanism establishes who is communicating.
2. **Application-level attestation:** a signed response binds the result to the exact request, evidence, execution context, and declared software/policy versions.

Transport authentication alone is insufficient because a trusted channel does not prove that a response belongs to the requested evidence. A signed payload alone is insufficient because signing does not establish that the peer is the expected service instance or endpoint.

## 3. Exchange flow

```text
EPM
 │
 │  ATTESTATION REQUEST
 │  request_id
 │  nonce
 │  request_digest
 │  evidence_id
 │  media_hash
 │  timestamp_claimed
 │  purpose / scope / jurisdiction
 │  consequence
 ▼
Verification Engine
 │
 │  validates request
 │  verifies evidence
 │  executes verification
 │  binds result to request
 │  signs attestation
 ▼
EPM
 │
 │  ATTESTATION RESPONSE
 │  request_id
 │  nonce
 │  request_digest
 │  response_digest
 │  evidence_id
 │  artifact_id
 │  result
 │  confidence
 │  engine_id / version
 │  policy_id / version
 │  oracle_versions
 │  processed_at
 │  freshness metadata
 │  signature / key id
 ▼
EPM Assurance Evaluation
 │
 ├── verify transport identity
 ├── verify signature
 ├── verify nonce / replay state
 ├── recompute request digest
 ├── verify evidence binding
 ├── verify response digest
 ├── verify freshness
 ├── verify engine/policy compatibility
 └── pass evidence into EPM Governor
```

## 4. Request contract

The canonical request should contain at minimum:

| Field | Purpose |
|---|---|
| `protocol_version` | Prevent incompatible interpretation |
| `request_id` | Unique correlation identifier |
| `nonce` | Replay resistance |
| `request_digest` | Canonical digest of signed request content |
| `evidence_id` | EPM evidence identity |
| `media_hash` | Exact artifact binding |
| `timestamp_claimed` | Temporal verification target |
| `purpose` | Downstream applicability |
| `scope` | Downstream applicability |
| `jurisdiction` | Rule applicability |
| `consequence` | Governor consequence class |
| `requested_operation` | Prevent confused-deputy use |
| `created_at` / `expires_at` | Request freshness |

Canonicalization must be deterministic. The digest must be calculated over a defined canonical representation, not an implementation-specific object serialization.

## 5. Response attestation contract

The response should contain at minimum:

| Field | Purpose |
|---|---|
| `protocol_version` | Contract version |
| `request_id` | Correlation |
| `nonce` | Replay binding |
| `request_digest` | Exact request binding |
| `response_digest` | Exact response-content binding |
| `evidence_id` | Evidence binding |
| `media_hash` | Artifact binding |
| `artifact_id` | Verification-engine identity |
| `result` | Verification result |
| `confidence` | Result confidence, not truth |
| `engine_id` | Verification service identity |
| `engine_version` | Executable provenance |
| `policy_id` / `policy_version` | Decision-rule provenance |
| `oracle_versions` | External dependency provenance |
| `processed_at` | Execution timestamp |
| `valid_until` | Freshness boundary |
| `signature` | Application-level authenticity/integrity |
| `key_id` | Signature-key rotation support |
| `attestation_status` | Explicit success/degraded/failure state |

## 6. Verification order

EPM must verify the response in this order before treating it as usable evidence:

1. Transport/service identity.
2. Protocol version compatibility.
3. Signature validity and key status.
4. Nonce and replay state.
5. Request digest equality.
6. Evidence ID and media-hash equality.
7. Response digest integrity.
8. Freshness and temporal applicability.
9. Engine identity/version authorization.
10. Policy identity/version compatibility.
11. Oracle provenance and declared degradation.
12. EPM applicability/integrity/provenance evaluation.
13. Governor decision.

A failure at an earlier layer must not be converted into a later successful state.

## 7. Replay protection

The receiver maintains replay state keyed by `(service_id, nonce)` or an equivalent scoped replay identifier. A request/response pair may be accepted only once within its validity window.

A repeated nonce with an identical response is still a replay. A repeated nonce with a different response is a replay plus a possible substitution attempt.

## 8. Freshness

`processed_at` proves when the engine claims to have processed the request; it does not prove that the underlying evidence was captured at that time. `timestamp_claimed`, oracle observation times, and engine processing time remain separate temporal facts.

Freshness policy must therefore be explicit and consequence-sensitive. Stale attestations are not silently treated as current attestations.

## 9. C2PA integration

C2PA should enter through an **Evidence/Provenance Adapter**, not through the Governor.

```text
Asset
  ↓
C2PA validation
  ↓
C2PA evidence witness
  ↓
EPM Evidence Envelope
  ↓
EPM applicability / provenance / integrity
  ↓
Governor
```

The adapter should preserve, at minimum:

- manifest identity/hash
- signer identity
- validation status
- content binding status
- ingredient relationships
- claim/assertion identifiers
- validation time
- trust/signing metadata needed for later re-validation

**Invariant:** `C2PA valid` never implies `EPM authorized`.

C2PA is evidence about provenance and integrity of an asset's provenance assertions. EPM remains responsible for whether that evidence is applicable to the requested use.

## 10. SOC 3 / control assurance

SOC 3 is not part of the runtime wire protocol. It is organizational/control assurance.

A future **Control Assurance Registry** may record:

- organization/service identity
- control framework
- report identifier
- assessment period
- auditor/assurance provider
- control scope
- applicable services
- exceptions or qualifications
- validity period
- source/report hash

The registry can inform risk posture or deployment eligibility, but it must not become a runtime claim that a particular verification result is true.

## 11. Failure states

The exchange should use explicit non-success states, including:

- `UNAUTHENTICATED_PEER`
- `INVALID_SIGNATURE`
- `REPLAY_DETECTED`
- `REQUEST_BINDING_MISMATCH`
- `EVIDENCE_BINDING_MISMATCH`
- `RESPONSE_INTEGRITY_FAILURE`
- `STALE_ATTESTATION`
- `ENGINE_NOT_AUTHORIZED`
- `POLICY_MISMATCH`
- `ORACLE_PROVENANCE_UNRESOLVED`
- `ATTESTATION_DEGRADED`
- `ATTESTATION_UNAVAILABLE`

These states must remain distinguishable in the audit record even where the external API maps several of them to the same HTTP status.

## 12. Audit binding

The EPM audit record should bind the exchange identifiers and hashes into the existing hash chain:

```text
claim/evidence
    + request_digest
    + response_digest
    + engine_id/version
    + policy_id/version
    + oracle_versions
    + attestation status
    + processed_at
    + signature key id
        ↓
immutable audit record
        ↓
previous_hash / record_hash
```

This creates a reconstructable chain from evidence to verification service assertion to EPM decision.

## 13. Threats addressed

| Threat | Primary control |
|---|---|
| Response substitution | Request/response digest binding |
| Replay | Nonce + replay state + validity window |
| Cross-claim attachment | Evidence ID + media hash binding |
| Wrong service | mTLS/service identity + engine authorization |
| Wrong software version | Engine version binding |
| Wrong policy | Policy identity/version binding |
| Oracle substitution | Oracle-version/provenance binding |
| Payload alteration | Signed response + response digest |
| Confused deputy | Requested operation + context binding |
| Stale result | Freshness/valid-until policy |
| C2PA over-trust | Adapter boundary + EPM Governor |
| SOC 3 over-trust | Separate control-assurance registry |

## 14. Implementation phases

### Phase A — Contract-only

Define canonical schemas, canonicalization, failure taxonomy, digest algorithm, signature envelope, key identifiers, freshness semantics, and audit fields.

### Phase B — Local loopback

Implement a test-only EPM ↔ FAP-Core exchange with deterministic keys and an in-process transport. Prove substitution, replay, wrong-evidence, wrong-policy, and stale-attestation failures.

### Phase C — Authenticated transport

Add service identity and mTLS. Bind the authenticated service identity to `engine_id` authorization.

### Phase D — C2PA adapter

Implement C2PA validation as an evidence source. Preserve raw validation facts and avoid translating them directly into an authorization decision.

### Phase E — Control Assurance Registry

Represent SOC 3 and related control-assurance metadata as independently versioned organizational evidence.

### Phase F — Production exchange

Deploy with key rotation, certificate rotation, replay persistence, clock policy, observability, incident handling, and disaster recovery.

## 15. Non-goals

This specification does not:

- assert that any verification engine produces truth;
- make C2PA a decision authority;
- make SOC 3 a runtime authorization token;
- replace EPM applicability or Governor semantics;
- require a specific cryptographic library before the canonical contract is fixed.

## 16. Acceptance criterion

A successful exchange must let an auditor or downstream verifier reconstruct:

> **which service** produced **which result**, for **which exact evidence**, in response to **which exact request**, under **which engine/policy/oracle versions**, at **what time**, with **what freshness**, and whether EPM subsequently authorized that result for the requested purpose, scope, jurisdiction, and consequence.

That is the assurance boundary. It is not a truth guarantee.
