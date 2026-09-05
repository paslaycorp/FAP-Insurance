# C2PA Provenance Adapter v0.1

**Status:** Architecture specification / implementation deferred

## Role

Convert validated C2PA provenance facts into EPM evidence without converting provenance validity into authorization.

```text
Asset / C2PA manifest → validator → provenance adapter → Evidence Envelope → EPM → Governor
```

## Preserve

- manifest identity/canonical hash
- signer identity and key/certificate identifiers
- signature and validation status
- content-binding result
- ingredient relationships
- assertion/action identifiers
- validation time
- trust/revocation material used
- validator implementation/version
- validation warnings/errors
- source artifact media hash

Do not collapse these facts to a boolean before creating the Evidence Envelope.

## Binding

C2PA evidence must bind to the exact artifact presented to EPM:

`C2PA content binding → media_hash → evidence_id`

An ingredient's provenance does not automatically transfer across a material transformation.

## Treatment

| Observation | EPM treatment |
|---|---|
| Valid manifest and content binding | Provenance witness available |
| Valid signature, unresolved trust | Evidence present; trust unresolved |
| No manifest | No C2PA witness |
| Malformed manifest | Degraded/invalid evidence |
| Invalid signature | Contradictory/invalid provenance evidence as policy dictates |
| Content-binding mismatch | Integrity contradiction |
| Validator unavailable | Unknown/degraded, never silently valid |

Exact mapping into EPM states remains policy-controlled.

## Re-validation

Record validation time and validator/trust-material metadata so later review can distinguish ingestion-time observation from later re-validation.

## Invariants

1. C2PA never bypasses EPM context checks.
2. C2PA signer identity never becomes authority for an unrelated downstream purpose.
3. Provenance does not automatically transfer across material transformations.
4. Missing C2PA is not represented as valid C2PA.
5. Failed validation cannot become normal success.
6. C2PA fields remain inside the immutable audit payload.

## Tests

Valid manifest; invalid signature; invalid content binding; missing manifest; unresolved trust; revoked/stale trust material; wrong media hash; ingredient substitution; validator failure; complete audit serialization.
