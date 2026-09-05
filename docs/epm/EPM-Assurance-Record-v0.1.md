# EPM Versioned Assurance Record v0.1

**Status:** Architecture specification — normative draft

## 1. Purpose

The Assurance Record is the durable, externally verifiable representation of an EPM assurance evaluation.

It is intended to make a decision reproducible as an event with explicit inputs, evidence, context, rules, transitions, and outcomes rather than as an opaque score.

## 2. Record identity

A record SHOULD contain:

```text
record_id
record_version
request_id
evidence_id
claim_id
created_at
```

`record_id` identifies the assurance event. It MUST NOT be reused for a materially different event.

## 3. Required semantic content

A record SHOULD bind:

- evidence references and hashes;
- provenance observations;
- integrity findings;
- identity context;
- purpose;
- scope;
- jurisdiction;
- evaluation time;
- governing rule and version;
- authority;
- source state;
- target state;
- transition identifier;
- preservation proof or explicit absence/failure;
- assurance result;
- failure code;
- consequence;
- Governor decision;
- engine and adapter versions;
- external attestation references where applicable.

## 4. Canonical representation

The record format MUST define a canonical serialization before cryptographic signing is introduced.

Canonicalization MUST specify treatment of:

- field ordering;
- omitted values;
- null values;
- timestamps;
- numbers;
- Unicode;
- enumerations;
- nested collections.

## 5. Integrity

A signed record SHOULD bind a digest of the canonical record body.

Where records are chained, each record SHOULD include the digest of its immediate predecessor.

A verifier MUST be able to distinguish:

- record-content modification;
- predecessor-link modification;
- missing predecessor;
- invalid signature;
- unknown signer;
- expired/revoked signing credential.

## 6. Reproducibility

An assurance record MUST preserve identifiers and versions sufficient to determine which interpretation rules were active when the decision was made.

The record MUST NOT imply reproducibility when required external evidence has expired or disappeared. It should instead record the verification limitation.

## 7. Decision semantics

The record MUST preserve the distinction between:

```text
AssuranceResult
    -> Governor
        -> Decision
```

A decision such as `AUTHORIZED` MUST NOT be stored without the assurance state and relevant failure semantics that justified it.

## 8. Privacy and minimization

The record SHOULD bind hashes, identifiers, and references rather than unnecessary raw sensitive content.

Signing and audit mechanisms MUST NOT require credentials, API keys, or other secrets to be embedded in the assurance record.

## 9. Future ledger target

The initial implementation may remain file/database backed. The long-term target is an append-only assurance ledger with:

- immutable records;
- deterministic record identifiers;
- cryptographic integrity;
- key rotation support;
- signer identity;
- retention policy;
- verification tooling;
- export/import with integrity preservation.

The ledger is an evidence-preservation mechanism, not a truth oracle.
