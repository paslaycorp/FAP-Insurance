# Control Assurance Registry v0.1

**Status:** Architecture specification / implementation deferred
**Purpose:** Represent organizational/control assurance separately from runtime evidence and decisions.

## Principle

SOC 3 is evidence about an organization's system-level controls. It is not a runtime communication protocol and is not a cryptographic assertion that an individual claim verification result is true.

## Registry record

A control-assurance record should include:

- `organization_id`
- `service_id`
- `framework` (for example, SOC 3 / applicable Trust Services Criteria)
- `report_id`
- `report_hash`
- `assurance_provider`
- `assessment_period_start`
- `assessment_period_end`
- `service_scope`
- `control_scope`
- `exceptions_or_qualifications`
- `effective_at`
- `expires_at`
- `source_reference`
- `ingested_at`

## Runtime use

The registry may answer questions such as:

- Is this verification service within an assessed organizational scope?
- Is the assessment period current enough for the deployment policy?
- Are there disclosed exceptions relevant to the deployment?

It must not answer:

- Is this particular claim true?
- Is this particular verification result authorized?
- Is a particular piece of evidence authentic merely because the provider has a SOC 3 report?

Those questions remain inside EPM's evidence, applicability, and Governor layers.

## Assurance hierarchy

```text
Asset provenance       → C2PA / provenance witnesses
Verification execution → EPM Assurance Exchange
Organizational controls → Control Assurance Registry
Decision authorization → EPM Governor
```

These layers are complementary and must not be collapsed into a single trust score without an explicitly versioned policy.

## Future implementation

The registry should be read-only from runtime decision paths and updated through a separately governed ingestion process. Imported reports and source documents should be content-addressed so the exact control-assurance artifact used by a policy evaluation can be reconstructed later.
