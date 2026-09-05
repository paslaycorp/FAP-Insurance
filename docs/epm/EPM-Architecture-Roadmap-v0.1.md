# EPM Architecture Roadmap v0.1

**Status:** Planning baseline  
**Branch:** `feature/epm-assurance-architecture-v0.1`

This roadmap intentionally separates release-critical hardening from architectural expansion.

## Phase 0 — Production hardening

**Current workstream:** PR #2  
**Rule:** Do not contaminate the hardening PR with next-generation architecture.

Targets:

- fail-closed assurance behavior;
- request-context isolation;
- proof binding;
- audit-chain integrity;
- authentication boundaries;
- CI and Docker enforcement.

## Phase 1 — Core specification

Deliver:

- EPM Core Assurance Specification v0.1;
- explicit epistemic state semantics;
- assurance-property semantics;
- applicability and transition invariants;
- Governor boundary;
- audit invariants.

**Status:** Draft established in this branch.

## Phase 2 — Assurance Exchange

Deliver:

- request/response envelope;
- canonicalization;
- nonce and replay protection;
- request and response digests;
- evidence binding;
- service identity;
- signed application attestation;
- explicit failure states;
- audit integration.

**Status:** Contract drafted; implementation intentionally deferred.

## Phase 3 — Evidence Adapter contract

Deliver:

- common adapter boundary;
- C2PA provenance adapter;
- oracle adapter semantics;
- epistemic-origin preservation;
- source freshness/temporal alignment;
- adapter versioning.

**Status:** Contract drafted; implementation intentionally deferred.

## Phase 4 — Versioned Assurance Record

Deliver:

- canonical assurance record;
- deterministic serialization;
- cryptographic record binding;
- version and policy provenance;
- audit/ledger integration.

**Status:** Record contract drafted; implementation intentionally deferred.

## Phase 5 — Formal temporal model

Before implementation, specify:

- evaluation-time semantics;
- future-effective rule behavior;
- stale evidence semantics;
- temporal intervals and boundaries;
- clock/source disagreement;
- replay windows;
- trusted timestamp requirements.

This phase exists to prevent time semantics from being scattered across individual adapters and endpoints.

## Phase 6 — Reciprocal FAP-Core attestation

Implement the Assurance Exchange against FAP-Core.

Target:

```text
EPM
  -> authenticated request
  -> FAP-Core verification
  -> signed, request-bound attestation
  -> EPM verification
  -> EPM assurance evaluation
  -> Governor
```

The existing FAP-Core bearer-auth boundary MUST remain explicit until a stronger service-identity design is deployed.

## Phase 7 — Durable assurance ledger

Implement append-only persistence with:

- immutable records;
- integrity chaining;
- signer identity;
- retention controls;
- verification/export tooling;
- migration/version policy.

## Phase 8 — Operational service identity

Target production communication security:

```text
API Gateway
   |
   | TLS
   v
EPM
   |
   | mTLS / authenticated service identity
   v
FAP-Core
   |
   | signed application attestation
   v
EPM Assurance Ledger
```

Transport identity and application attestation remain separate controls.

## Phase 9 — Control-assurance registry

SOC 3-type organizational assurance belongs here, not in the runtime Governor.

Registry fields may include:

- organization;
- framework;
- assessment period;
- auditor;
- report identifier;
- control scope;
- exceptions;
- validity period.

Control assurance may establish confidence in the operating environment. It MUST NOT be treated as proof that an individual runtime claim is true.

## Phase 10 — General assurance substrate

Only after the preceding contracts stabilize should EPM be generalized as a reusable assurance protocol/library for domains beyond insurance.

### Architectural prohibitions

EPM MUST NOT evolve into:

- a universal trust score;
- a centralized truth oracle;
- a system where provenance automatically implies truth;
- a system where organizational compliance substitutes for runtime evidence;
- a system where a signed peer response bypasses EPM applicability or consequence controls.

### Change-control rule

Any proposed architectural change that materially changes assurance semantics requires an explicit decision record containing:

1. Finding
2. Threat/failure mode
3. Option A
4. Option B
5. Pros/cons
6. Blast radius
7. Effort
8. Recommendation

Low-risk tightening that preserves existing semantics may be implemented directly. Semantic expansion requires review.
