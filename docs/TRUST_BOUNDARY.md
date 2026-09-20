# FAP-Insurance Trust and Authority Boundary

## Purpose

This document answers one question: **who is allowed to assert what?**

The system separates evidence production, trust validation, epistemic evaluation, deployment authority, and operational observation. Crossing one boundary does not silently grant authority in another.

## Authority matrix

| Actor / component | May assert | May not assert |
| --- | --- | --- |
| External caller | claim inputs and authenticated request data | EPM preservation, boundary validation, producer/runtime identity |
| FAP-Core | verification result, canonical evidence receipt, producer identity, verification attestation | FAP-Insurance/EPM ingestion-boundary validation or downstream authorization |
| FAP-Insurance trusted validator | whether a canonical receipt is bound to the exact expected contract, evidence, provenance, chronology, producer, authenticated runtime identity, and local ingress | arbitrary downstream applicability outside the bound source context |
| EPM | assurance state and transition decision under supplied typed context/evidence | facts not established by evidence; FAP domain scoring |
| GitHub protected main + release workflow | reviewed source identity and production-release eligibility | semantic authorization of evidence |
| Render | hosting/deployment execution and provider state | source provenance or EPM decision authority |
| Operator | initiate permitted release/recovery actions and preserve evidence | manually manufacture assurance to bypass failed validation |

## Trusted FAP-Core → EPM path

The legitimate source-assurance path is:

`authenticated FAP-Insurance ingress`
→ `authenticated FAP-Core /verify`
→ `canonical EPM-FAP Evidence Receipt`
→ `exact contract revision`
→ `exact producer repository + commit`
→ `authenticated independently observed FAP-Core runtime identity`
→ `receipt/provenance/timestamp integrity checks`
→ `ValidatedFAPBoundary`
→ `bound EPM source state`
→ `EPM transition evaluation`

No shortcut is equivalent to this chain.

## Validator acceptance boundary

The validator accepts a receipt only when, among other checks:

- schema and contract version/revision are exact;
- receipt evidence ID matches the FAP response artifact ID;
- local authenticated evidence availability is trusted;
- provenance reference matches the FAP response;
- attestation authority, method, basis, and validation state are expected;
- FAP-Core does not self-assert ingestion-boundary validation;
- producer component/repository/commit are exact and well formed;
- authenticated FAP-Core runtime repository and SHA match the receipt producer;
- availability/observation chronology is coherent and fresh;
- receipt ID integrity binding matches the canonical material.

The current source context is deliberately narrow: claim-verification purpose, claim scope, TX jurisdiction, carrier-default rule version 1, carrier-authority. Expansion requires an explicit contract change and tests.

## Anti-authority rules

The following are never sufficient by themselves:

- `STRICT` or `PROBABLE`;
- high confidence or score;
- `boundary_validated=true` in raw input;
- caller-created `PreservationProof(boundary_validated=True)`;
- FAP-Core claiming its own EPM boundary validation;
- a healthy dependency;
- a Render `live` state;
- a green PR.

## Release authority boundary

Protected `main` is source authority. Production release is a separate manual exact-SHA action. Accepted release evidence must bind merged-PR provenance, required checks, exact candidate SHA, Render deployment, runtime identity, expected versions, dependency connectivity, and the release attestation.

Merging code does not itself change production.
