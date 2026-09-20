# FAP-Insurance Incident Response

## Purpose

This playbook covers production failures that can affect release integrity, FAP-Core trust, EPM authority, audit evidence, or service availability.

## Incident classes

### IR-1 — Authority or provenance integrity

Examples:

- an authorization appears without a valid trusted boundary;
- receipt producer SHA and observed FAP-Core runtime SHA disagree;
- runtime SHA differs from the attested release SHA;
- a raw or caller-supplied trust claim appears to influence EPM authority.

Response: highest priority. Freeze production releases, preserve evidence, and do not normalize the event as an ordinary availability failure.

### IR-2 — Release integrity

Examples:

- exact-SHA deployment cannot be proven;
- merged-PR provenance fails;
- rollback cannot prove the prior runtime;
- Render reports live but runtime identity is inconsistent.

Response: release is failed until identity is proven.

### IR-3 — Dependency trust outage

Examples:

- FAP-Core authentication fails;
- authenticated runtime identity is unavailable;
- canonical receipt is missing, stale, malformed, or contradictory.

Response: preserve fail-closed behavior. Do not weaken the boundary to restore throughput.

### IR-4 — Availability degradation

Examples:

- FAP-Insurance process unavailable;
- non-authority external oracles degrade;
- latency or request failures increase while identity controls remain intact.

Response: restore service while preserving authority controls.

## Initial response

1. Record UTC detection time and operator.
2. Capture current production URL, runtime health response, current protected-main SHA, and last verified release attestation.
3. Freeze discretionary production releases.
4. Preserve relevant workflow run IDs, deployment IDs, request IDs, audit hashes, and logs.
5. Determine whether the incident touches authority/provenance integrity. If uncertain, classify upward.
6. Do not edit or delete audit records to repair appearances.

## Authority-boundary investigation

Check, in order:

1. local authenticated ingress evidence ID;
2. FAP response artifact ID and provenance hash;
3. canonical receipt schema and contract revision;
4. receipt attestation authority/method/basis;
5. producer repository and exact commit SHA;
6. authenticated FAP-Core runtime repository and commit identity;
7. receipt age and chronology;
8. resulting `ValidatedFAPBoundary` context binding;
9. EPM source/target context and final decision.

A FAP score or verdict is never acceptable substitute evidence for any missing step.

## Release failure investigation

Compare:

`merged PR → merge SHA → successful CI for SHA → Render deployment ID/SHA → runtime SHA → EPM version → FAP version → FAP-Core connectivity → attestation`

The first broken edge is the failure boundary. Do not claim later edges as established if an earlier edge is missing.

## Rollback decision

Rollback when production mutation occurred and the new runtime cannot prove the release acceptance chain. Prefer the last deployment with a retained verified attestation.

Do not rollback merely to change an EPM decision outcome. Semantic disagreement is investigated as evidence/context, not repaired by selecting a more permissive binary.

## Recovery criteria

Close an incident only when:

- the affected trust/release edge is understood;
- runtime identity is again proven;
- hostile input remains non-authoritative;
- a legitimate matching-context path functions when its evidence is valid;
- rollback/recovery evidence is retained;
- no unsupported assurance claim was made during recovery.

## Post-incident record

Record facts separately from hypotheses:

- timeline;
- exact source/runtime identities;
- affected requests and audit references;
- observed failure;
- containment;
- recovery;
- root cause if established;
- unresolved questions;
- corrective controls;
- verification evidence.

If root cause is not established, state that explicitly.
