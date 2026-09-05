# C2PA Provenance Adapter v0.1

**Status:** Architecture specification / implementation deferred
**Parent:** EPM Assurance Exchange v0.1

## Role

The C2PA adapter converts externally validated C2PA provenance facts into EPM evidence without converting provenance validity into an authorization decision.

```text
C2PA asset/manifest
        ↓
C2PA validator
        ↓
Provenance Adapter
        ↓
Evidence Envelope
        ↓
EPM assurance evaluation
        ↓
Governor
```

## Required preservation

The adapter must preserve enough information to re-evaluate the provenance assertion later:

- manifest identifier and/or canonical manifest hash
- signer identity and certificate/key identifiers where available
- signature/validation status
- content-binding result
- ingredient references and relationships
- assertion/action identifiers
- validation timestamp
- trust-list / certificate status information used during validation
- validator implementation/version
- validation errors/warnings
- source artifact media hash

The adapter must not reduce this to a single boolean before the Evidence Envelope is created.

## State mapping

C2PA outcomes should be represented as evidence states rather than verdicts:

| C2PA observation | EPM treatment |
|---|---|
| Valid manifest + valid content binding | Provenance witness available |
| Valid signature but unresolved trust | Provenance evidence present; trust unresolved |
| Manifest absent | No C2PA witness |
| Manifest malformed | Degraded/invalid C2PA evidence |
| Signature invalid | Contradictory/invalid provenance evidence as appropriate |
| Content binding mismatch | Integrity contradiction |
| Validation unavailable | Unknown/degraded; never silently valid |

The exact mapping to EPM `AssuranceState` must remain policy-controlled.

## Binding requirements

C2PA evidence must bind to the exact artifact presented to EPM. A valid manifest for another byte sequence is not evidence for the current artifact.

At minimum:

`C2PA content binding → media_hash → evidence_id`

The adapter should also retain ingredient relationships without assuming that an ingredient's provenance transfers automatically to the derived artifact.

## Re-validation

C2PA validation is time-sensitive where trust lists, certificate status, or revocation information can change. The envelope must record the validation time and validator metadata so a later audit can distinguish:

- what was observed at ingestion;
- what was subsequently revalidated;
- what trust material was used.

## Security invariants

1. C2PA validation never bypasses EPM context checks.
2. C2PA signer identity never becomes authority for an unrelated downstream purpose.
3. C2PA provenance does not automatically transfer across material transformations.
4. Missing C2PA data is not represented as valid C2PA data.
5. Failed C2PA validation is not converted into a normal success response.
6. C2PA facts are included in the immutable audit payload.

## Testing requirements

The future implementation must test at least:

- valid manifest;
- invalid signature;
- invalid content binding;
- missing manifest;
- unresolved signer trust;
- stale/revoked trust material;
- manifest bound to a different media hash;
- ingredient substitution;
- validator failure;
- preservation of all C2PA fields through audit serialization.
