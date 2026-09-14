# EPM vNext Engine — Integration Surface

## Status

This document describes the vNext branch implementation under review. It does not modify the frozen EPM v0.2 closure claim and it is not a release declaration.

## Public Python interface

Domain-neutral callers should import from `epm`:

```python
from epm import (
    EPM_ENGINE_VERSION,
    EvidentiaryEnvelope,
    EvidentiaryState,
    assess_transition,
    inspect_state,
)
```

The public façade exposes two primary operations.

### `assess_transition(envelope)`

Evaluates whether an assurance property survives a proposed source-to-target transition under the declared context, rule binding, materiality, preservation proof, and consequence.

This path preserves the existing distinctions between evidence validity, applicability, and authorization.

### `inspect_state(state)`

Inspects a domain-neutral evidentiary snapshot and returns typed component results for:

- epistemic source records;
- evidence-availability provenance;
- first-class constraints;
- answer-space representation;
- justification/dependency graph integrity;
- declared limitations;
- unresolved conditions.

The report intentionally contains no master confidence score and no authorization decision.

## Implemented semantic modules

- `epm_envelope.py` — generic transition envelope and evaluation
- `epm_temporal.py` — trusted evidence-availability provenance semantics
- `epm_sources.py` — epistemic source typing
- `epm_constraints.py` — premise/provenance/entailment-aware constraints
- `epm_resolution.py` — answer-space, discriminator, resolution, and closure state
- `epm_justification.py` — support graph, cycle detection, independence, invalidation propagation
- `epm_state.py` — aggregate domain-neutral evidentiary state
- `epm_engine.py` — stable façade
- `epm_fap_adapter.py` / `epm_fap_semantics.py` — compatibility bridge for the existing insurance runtime

## FAP compatibility

The current FAP-Insurance request model remains supported. Its transition path is translated into the generic EPM envelope and then evaluated through the same engine semantics.

The compatibility path deliberately does not fabricate semantic objects that the insurance endpoint does not possess.

In particular:

- `timestamp_claimed` is not evidence availability;
- `capture_time` is not automatically evidence availability;
- `processed_at` is not historical evidence availability;
- the existence of the typed availability module does not make production C-21 conformant without a trustworthy production provenance source.

## Failure behavior

EPM preserves typed failure/uncertainty states rather than coercing them into booleans.

Examples:

- UNKNOWN remains UNKNOWN/DEFER when required assurance is not established;
- material context changes fail closed without valid preservation;
- unsupported constraints do not narrow the answer-space;
- singleton narrowing does not become resolution;
- computation does not become observation;
- a discriminator definition does not become its outcome observation;
- circular or shared-origin support does not manufacture independence;
- invalidated dependencies propagate staleness downstream;
- state inspection does not authorize an action.

## Versioning

The current public engine version is `epm-engine/0.1`.

Schema versions are explicit in the generic transition envelope and aggregate evidentiary state so later semantic expansion cannot silently change the meaning of previously serialized objects.

## Current non-claims

This branch does not claim:

- production C-21 conformance for the FAP endpoint;
- a real-world trusted availability connector where none exists;
- that every production domain already emits source, constraint, answer-space, or justification objects;
- that a clean justification graph authorizes a decision;
- that all EPM vNext code is merged or released.

TVC and Variant Hunter remain outside this implementation cycle.
