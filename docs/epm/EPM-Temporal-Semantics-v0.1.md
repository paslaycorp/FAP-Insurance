# EPM Temporal Semantics v0.1

**Status:** Architecture specification — normative draft

## 1. Purpose

Time is an assurance dimension. EPM MUST distinguish the time at which a claim says something occurred from the time at which evidence was observed, processed, signed, or evaluated.

## 2. Required time fields

Where applicable, an assurance record SHOULD distinguish:

- `claimed_at` — time asserted by the claim;
- `observed_at` — time associated with an external observation;
- `captured_at` — artifact/device capture time;
- `processed_at` — verification execution time;
- `effective_at` — governing rule/policy effective time;
- `evaluated_at` — EPM evaluation time;
- `received_at` — service receipt time.

These fields MUST NOT be silently substituted for one another.

## 3. Temporal applicability

A rule is applicable only when its effective interval contains the relevant evaluation time according to the rule's defined boundary semantics.

A future-effective rule MUST NOT establish present applicability merely because its version is known to the evaluator.

## 4. Evidence freshness

Freshness is an evidence property, not an automatic validity guarantee.

Each time-sensitive adapter SHOULD define:

- observation timestamp;
- maximum acceptable age;
- clock/source assumptions;
- stale behavior;
- discrepancy behavior.

A stale observation MUST be explicitly marked stale or unavailable. It MUST NOT be silently relabeled as current.

## 5. Temporal alignment

When an oracle is used to evaluate a historical claim, the implementation SHOULD select evidence using a documented temporal alignment rule.

A source observation that is merely recent relative to processing time is not necessarily relevant to the claim time.

## 6. Clock disagreement

Independent time sources may disagree. EPM SHOULD preserve the disagreement rather than selecting a preferred timestamp without recording the basis for that choice.

Material temporal disagreement MUST be capable of producing `TEMPORAL_MISMATCH`, `DEFER`, `QUARANTINE`, or `DENY` according to consequence and policy.

## 7. Replay windows

Replay protection MUST use an explicit validity window. A response outside that window MUST NOT become valid solely because its cryptographic signature remains valid.

## 8. Trusted timestamps

Where a trusted timestamp authority is used, the assurance record SHOULD identify the authority and timestamp evidence separately from the originating system's claimed creation time.

## 9. Boundary conditions

Implementations MUST define behavior for:

- exact effective-time boundaries;
- clock skew;
- timezone normalization;
- leap/ambiguous local times;
- missing timestamps;
- future timestamps;
- contradictory timestamps;
- timestamp precision loss.

## 10. Security invariant

No single timestamp field may be treated as proof of temporal truth. Temporal assurance is the result of explicit comparison among the relevant time assertions, source characteristics, rule applicability, and consequence.
