# EPM Assurance Exchange v0.1
## Reciprocal machine-to-machine assurance contract

**Status:** Architecture specification — implementation baseline  
**Scope:** EPM ↔ trusted verification-engine communication  
**Initial peer:** FAP-Core  
**Transport:** TLS; production target includes authenticated service identity/mTLS  
**Application integrity:** signed attestation record

## 1. Objective

The Assurance Exchange binds a verification result to the exact request, evidence, context, engine, policy, and execution event that produced it.

The exchange MUST prevent or detect:

- response substitution;
- replay;
- cross-claim attachment;
- stale-result reuse;
- engine/version substitution;
- policy mismatch;
- intermediary modification;
- confused-deputy use of a verification service.

The intended statement is:

> The identified verification engine produced this exact attestation for this exact request and evidence under the identified execution and policy context.

This is an attestation of system execution and binding, not a declaration of objective truth.

## 2. Request envelope

The request SHOULD contain:

```text
request_id
nonce
request_digest
claim_id
evidence_id
media_hash
timestamp_claimed
purpose
scope
jurisdiction
rule_id
rule_version
authority
consequence
requested_at
requester_service_id
```

`request_digest` MUST be computed over a canonical representation of all security-relevant request fields **excluding `request_digest` itself**.

`nonce` MUST be unique for the request lifetime and retained sufficiently to reject replay.

## 3. Response attestation

The response SHOULD contain:

```text
request_id
nonce
request_digest
response_digest
evidence_id
artifact_id
engine_id
engine_version
policy_id
policy_version
oracle_versions
processed_at
result
confidence
failure_state
responder_service_id
signature
```

`response_digest` MUST cover the canonical response payload **excluding both `response_digest` and `signature`**. This avoids circular hashing while binding every other security-relevant response field.

The response MUST carry the original `request_digest` and `nonce`, allowing the requester to verify correlation without trusting an intermediary's routing metadata.

## 4. Verification order

EPM MUST verify the response in this order or an equivalent fail-closed order:

1. Transport/service identity.
2. Request identifier and nonce correlation.
3. Replay status.
4. Request digest equality.
5. Evidence binding.
6. Response signature.
7. Response digest.
8. Engine identity/version.
9. Policy identity/version.
10. Temporal validity.
11. Result semantics and failure state.
12. EPM applicability and transition rules.

Successful cryptographic verification MUST NOT bypass the final EPM assurance evaluation.

## 5. Replay protection

A previously accepted `(responder_service_id, nonce, request_digest)` tuple MUST NOT be accepted again as a new execution.

A replay cache or durable equivalent MUST have a defined retention period and fail closed when replay state cannot be evaluated for a security-critical operation.

## 6. Canonicalization

Request and response digests MUST use a deterministic canonical serialization. Implementations MUST specify:

- field names;
- field ordering;
- encoding;
- Unicode normalization policy;
- timestamp representation;
- treatment of omitted/null fields;
- numeric representation.

Ad hoc JSON serialization MUST NOT be assumed to be canonical merely because two payloads appear equivalent.

## 7. Service identity

Transport authentication and application attestation solve different problems.

- **mTLS/service identity:** establishes who is communicating.
- **Signed application attestation:** establishes what the identified service claims it executed and produced.

A mature deployment SHOULD use both.

## 8. Failure behavior

If identity, binding, replay status, signature, digest, policy, temporal validity, or required context cannot be established, the exchange MUST return an explicit non-success state.

The consumer MUST NOT substitute a local success value for an unverifiable peer result.

## 9. Audit integration

The accepted or rejected exchange MUST produce an audit event containing enough information to reconstruct the binding decision without storing unnecessary secrets.

At minimum, the audit event SHOULD bind:

- request ID;
- request digest;
- response digest, when present;
- evidence ID;
- peer service identity;
- engine/policy versions;
- verification outcome;
- replay outcome;
- timestamp;
- resulting EPM assurance decision.

## 10. FAP-Core integration boundary

The current FAP-Core `/verify` bearer-auth contract is a separate transport/application concern from this exchange. EPM MUST NOT silently weaken that contract to make integration work.

The implementation phase MUST establish an explicit service credential/identity model and then add application-level attestation binding.

## 11. Security invariant

No response may be accepted solely because:

- it came from a reachable endpoint;
- its HTTP status was successful;
- its confidence score is high;
- its engine name is familiar;
- its artifact ID exists;
- its signature is valid without request/evidence binding.

Acceptance requires the complete binding chain.
