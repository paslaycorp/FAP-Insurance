# Control Assurance Registry v0.1

**Status:** Architecture specification / implementation deferred

## Principle

SOC 3 is organizational/control assurance, not a runtime communication protocol and not a cryptographic assertion that an individual verification result is true.

## Record

Store:

- `organization_id`
- `service_id`
- `framework`
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

The registry may inform deployment eligibility, scope coverage, freshness, or disclosed control exceptions. It must not answer whether an individual claim is true or whether an individual verification result is authorized.

## Assurance hierarchy

```text
Asset provenance         → C2PA / provenance witnesses
Verification execution   → EPM Assurance Exchange
Organizational controls  → Control Assurance Registry
Decision authorization   → EPM Governor
```

The layers are complementary and must not be collapsed into a single trust score without an explicitly versioned policy.

## Future implementation

Keep runtime access read-only. Ingest source reports through a separately governed process. Content-address imported reports so the exact control-assurance artifact used by policy evaluation can be reconstructed.
