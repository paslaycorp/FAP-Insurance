# EPM — Evidentiary Provenance Model
## Core Assurance Specification v0.1

**Status:** Architecture specification — normative draft  
**Scope:** Core assurance semantics and boundaries  
**Implementation target:** FAP-Insurance / EPM  
**Non-goal:** This specification does not assert that EPM determines objective truth.

## 1. Purpose

EPM determines what decision is **epistemically admissible** from available evidence, provenance, integrity, applicability, authority, temporal context, transition semantics, and consequence.

EPM MUST NOT collapse these dimensions into a single undifferentiated trust score.

The central question is:

> Given an evidence state, its provenance and integrity, the applicable context and governing rule, and the consequence of action, what decision is admissible?

## 2. Assurance boundary

The reference processing boundary is:

```text
Input
  -> Authentication
  -> Context
  -> Evidence
  -> Provenance
  -> Integrity
  -> Applicability
  -> Transition
  -> Preservation Proof
  -> Assurance Result
  -> Governor
  -> Decision
  -> Audit
  -> External Assurance Record
```

Every boundary MUST reject, quarantine, defer, or explicitly represent uncertainty when its required invariant cannot be established.

## 3. Epistemic states

The core state vocabulary is:

- `UNKNOWN` — required assurance has not been established.
- `PRESERVED` — required assurance survived the evaluated transition.
- `CHANGED` — the underlying state changed without necessarily implying invalidity.
- `INVALIDATED` — required assurance was not preserved.
- `CONTRADICTED` — material evidence or state assertions conflict.
- `VALID` — compatibility state for an established source condition.

`UNKNOWN` MUST NOT be interpreted as permission.

`CONTRADICTED` MUST NOT be interpreted as permission.

## 4. Assurance properties

EPM treats at least these properties independently:

- Integrity
- Provenance
- Identity
- Evidence
- Applicability

A property may depend on other properties, but dependency MUST remain explicit. A failure in one dimension MUST NOT be silently converted into success in another dimension.

## 5. Applicability context

An assurance context may include:

- identity
- purpose
- scope
- jurisdiction
- effective time
- governing rule
- rule version
- authority
- consequence

A valid artifact MAY still be inapplicable. EPM therefore treats context as part of assurance, not metadata decoration.

## 6. Transition semantics

A transition evaluates whether assurance established for a source state remains admissible for a target state.

Material transition dimensions include:

- identity
- purpose
- scope
- jurisdiction
- time
- rule
- rule version
- authority

A material transition requires an explicit preservation proof. Omission of a required target binding MUST NOT be treated as equivalent to a matching binding.

## 7. Preservation proof

A preservation proof MUST identify, at minimum:

- assurance property
- transition identifier
- governing rule identifier and version
- authority
- evidence references
- validity
- reason
- source/target applicability bindings required by the evaluated property

A proof is insufficient when:

- it is invalid;
- it references the wrong transition;
- it references the wrong governing rule or version;
- it references a future-effective rule for the evaluation time;
- evidence references are absent;
- required context bindings are absent or contradictory.

## 8. Governor

The Governor is a decision-admissibility boundary. It MUST NOT independently manufacture preservation or evidence validity.

Reference decisions:

- `AUTHORIZED`
- `AUTHORIZED_WITH_CONSTRAINTS`
- `DEFER`
- `QUARANTINE`
- `DENY`

Critical consequences MUST fail closed when required assurance is not established.

## 9. Failure semantics

Material assurance failures include, at minimum:

- misapplication
- authority mismatch
- jurisdiction mismatch
- temporal mismatch
- rule mismatch
- unresolved composition
- preservation unestablished
- contradictory evidence

Failure codes MUST preserve the reason for non-admissibility. A generic failure code MUST NOT replace a more specific established cause.

## 10. Audit invariants

Audit records MUST be bound to the event they represent and to the preceding record where a chain is used.

A chain integrity check MUST detect both:

1. predecessor-link tampering (`previous_hash_mismatch`); and
2. record-content tampering (`record_hash_mismatch`).

Audit serialization MUST fail rather than invent an assurance result when required serialization data cannot be represented faithfully.

## 11. External evidence

External systems, oracles, provenance formats, and verification engines are evidence providers. Their assertions MUST enter EPM through explicit adapters or assurance-exchange contracts.

External evidence MUST NOT bypass EPM applicability, transition, authority, temporal, consequence, or Governor controls.

## 12. Non-goals

EPM is not:

- a universal truth oracle;
- a centralized trust score;
- a replacement for source-system verification;
- an organizational compliance certification;
- a claim that valid provenance proves the truth of a claim.

## 13. Conformance principle

An implementation conforms to EPM v0.1 only if it preserves the separation between:

**evidence → provenance/integrity → applicability → transition → assurance → governance → decision**.

Any implementation that allows a lower-assurance condition to silently become a higher-assurance decision is non-conformant.
