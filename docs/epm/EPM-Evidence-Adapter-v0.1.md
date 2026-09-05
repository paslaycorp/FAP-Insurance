# EPM Evidence Adapter Contract v0.1

**Status:** Architecture specification — normative draft

## 1. Purpose

An Evidence Adapter converts an external provenance or oracle result into an EPM Evidence Envelope without granting that external system authority over the final decision.

Adapters are the boundary between heterogeneous evidence providers and the EPM assurance model.

## 2. Adapter responsibilities

An adapter MUST:

- identify the evidence source;
- preserve source timestamps;
- preserve source status and discrepancy information;
- retain cryptographic identifiers where available;
- distinguish observed data from derived or inferred values;
- preserve source failure conditions;
- produce deterministic evidence identifiers where the source provides a stable identity;
- avoid fabricating confidence or validity.

## 3. Evidence classes

Adapters SHOULD classify observations according to their epistemic origin:

```text
OBSERVED
EVIDENCED
DERIVED
INFERRED
PREDICTED
SIMULATED
COUNTERFACTUAL
```

A derived or inferred observation MUST NOT be serialized as though it were directly observed.

## 4. C2PA adapter

The initial C2PA adapter SHALL treat C2PA as a provenance witness.

Reference path:

```text
Asset
  -> C2PA validation
  -> C2PA evidence
  -> Evidence Envelope
  -> EPM provenance/integrity evaluation
  -> applicability/transition evaluation
  -> Governor
```

A valid C2PA manifest does not by itself establish claim truth, applicability, authority, or admissibility.

The adapter SHOULD preserve, where available:

- manifest identifier;
- claim identifier;
- signer identity;
- signature validation status;
- content binding status;
- ingredient relationships;
- claimed creation time;
- trusted timestamp information;
- revocation/trust information;
- validation findings.

## 5. Oracle adapter

Oracle adapters MUST preserve the distinction between:

- source observation;
- source freshness;
- temporal alignment to the claim;
- source failure;
- source discrepancy;
- local derivation.

A stale observation MUST NOT silently become a current observation.

## 6. Confidence

Adapter-level confidence is evidence metadata. It is not an EPM decision score.

Confidence MUST NOT override a failed material applicability, provenance, integrity, authority, or preservation invariant.

## 7. Failure behavior

If an adapter cannot faithfully represent a source observation, it MUST fail or mark the observation unavailable. It MUST NOT invent a substitute value solely to keep the pipeline running.

For security-critical evaluation, unavailable evidence MUST remain unavailable to downstream decision logic.

## 8. Versioning

Each adapter SHOULD expose:

- adapter ID;
- adapter version;
- source/provider identity;
- source version/API version where known;
- validation timestamp.

Changes to interpretation rules MUST increment the adapter version or associated policy version so that assurance records remain reproducible.

## 9. Separation rule

Evidence adapters collect and normalize evidence. They do not:

- authorize actions;
- classify consequences;
- establish preservation across arbitrary contexts;
- bypass the Governor;
- convert uncertainty into certainty.
