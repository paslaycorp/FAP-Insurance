# EPM C2PA Integration v0.1

**Status:** Architecture specification — integration boundary

## 1. Role of C2PA

C2PA is an artifact-level provenance mechanism. In EPM it is a provenance witness, not the final assurance or decision engine.

Reference flow:

```text
Artifact
  -> C2PA validation
  -> C2PA evidence
  -> EPM Evidence Envelope
  -> provenance/integrity evaluation
  -> applicability
  -> transition/preservation
  -> Governor
  -> decision
```

## 2. Evidence preserved from C2PA

The adapter SHOULD preserve available:

- manifest identity;
- claim identity;
- signer identity;
- signature validation result;
- content binding result;
- ingredient relationships;
- claimed creation time;
- trusted timestamp information;
- revocation information;
- validation findings.

## 3. Trust separation

The following statements are deliberately distinct:

1. The manifest is cryptographically valid.
2. The signer identity is trusted for the relevant purpose.
3. The artifact binding is valid.
4. The provenance history is complete enough for the relevant question.
5. The artifact is applicable to the target context.
6. The artifact supports the claim being evaluated.

A successful statement at one layer MUST NOT be silently promoted into another.

## 4. Missing or invalid provenance

Missing C2PA data does not automatically imply that an artifact is false. It means that the C2PA provenance channel did not establish the relevant property.

Invalid C2PA data MUST remain distinguishable from absent C2PA data.

## 5. Multiple manifests and ingredients

When an asset references ingredients or prior manifests, the adapter SHOULD preserve the relationship graph sufficiently for EPM to determine whether provenance continuity is relevant to the evaluation.

A valid child manifest MUST NOT automatically validate every upstream ingredient for every purpose.

## 6. Signer and organizational assurance

Signer identity and organizational control assurance are separate dimensions.

A signer certificate or organizational control report MAY provide evidence about identity or operating controls, but neither independently establishes claim truth.

## 7. Versioning

The adapter MUST record the C2PA specification/implementation version when available and MUST version any local interpretation rules.

## 8. Implementation boundary

The existing EPM evidence model already has C2PA fields. The implementation task is to connect a real validator through an adapter without allowing the adapter to bypass EPM's existing applicability, preservation, consequence, or Governor semantics.

## 9. Security invariant

`C2PA valid` MUST never be equivalent to `EPM authorized`.
