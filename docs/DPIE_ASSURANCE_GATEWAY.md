# DPIE Assurance Gateway

## Purpose

FAP verifies evidence. DPIE evaluates whether an assurance property established at one epistemic state may legitimately support a downstream state after a material transition.

## Governing invariant

For a material transition:

`Q1 -> Q2`

an assurance property `P(Q1)` SHALL NOT be used as evidence that `P(Q2)` holds unless an explicit preservation relation establishes that inference.

Formally:

`P(Q1) !=> P(Q2)` without `Preserve(T, P)`.

## What DPIE does not claim

DPIE does not guarantee truth, complete evidence, complete world knowledge, safe consequences, or universal semantic completeness. It prevents an unestablished assurance relationship from being silently represented as established.

## Required dimensions

A downstream determination is bound to:

- state
- property
- context
- transition
- evidence
- rule identity/version
- authority

The following relationships are explicitly non-transitive unless separately established:

- integrity -> applicability
- provenance -> applicability
- verification -> authority
- applicability -> authority
- authority -> safety
- valid component -> valid composite

## Canonical adversarial test

Start with a perfectly authentic, intact, correctly provenanced artifact. Change only its application purpose or jurisdiction. If the system continues to treat the original assurance as sufficient, it has an epistemic inheritance failure.

Expected result:

- integrity: VALID
- provenance: VALID
- applicability: INVALIDATED or UNKNOWN
- failure: MISAPPLICATION or jurisdiction mismatch
- consequential decision: QUARANTINE or DENY

No tampering is required.

## Integration boundary

The initial implementation is intentionally dependency-light and isolated in `dpie_assurance.py`. It can be called after FAP evidence fusion and before a consequential business decision. It does not replace the existing FAP evidence envelope, oracle, fusion, or audit mechanisms.

## Next integration step

Wire the transition evaluator into the insurance decision path and persist the DPIE determination alongside the existing audit record. The integration should bind the determination to the carrier rule identifier/version and the decision context rather than adding a generic `trusted=true` flag.
