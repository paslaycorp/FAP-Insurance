"""Adversarial gate for EPM epistemic source typing v0.1."""
from datetime import datetime, timezone

from dpie_assurance import AssuranceContext, AssuranceState, RuleBinding, State
from epm_envelope import EvidentiaryEnvelope, evaluate_evidentiary_envelope
from epm_sources import (
    EpistemicSourceRecord,
    EpistemicSourceType,
    computational_output_type,
    observation_reclassification_allowed,
    validate_source_record,
)

UTC = timezone.utc
AT = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)


def _source(
    source_type: EpistemicSourceType,
    *,
    external: bool = False,
    source_id: str = "SRC-1",
) -> EpistemicSourceRecord:
    return EpistemicSourceRecord(
        source_id=source_id,
        source_type=source_type,
        producer="test-producer",
        provenance_refs=(f"prov:{source_id}",),
        input_refs=("input:E-1",),
        external_origin=external,
    )


def test_discriminator_cannot_be_relabelled_as_observation_without_new_evidence():
    result = observation_reclassification_allowed(_source(EpistemicSourceType.DISCRIMINATOR))
    assert result.valid is False
    assert result.reason_code == "NEW_OBSERVATION_REQUIRED"


def test_computational_discovery_cannot_be_relabelled_as_observation_without_new_evidence():
    result = observation_reclassification_allowed(_source(EpistemicSourceType.COMPUTATIONAL_DISCOVERY))
    assert result.valid is False
    assert result.reason_code == "NEW_OBSERVATION_REQUIRED"


def test_computation_over_existing_inputs_retains_computational_source_type():
    assert computational_output_type() is EpistemicSourceType.COMPUTATIONAL_DISCOVERY


def test_observation_without_external_origin_is_invalid():
    result = validate_source_record(_source(EpistemicSourceType.OBSERVATION, external=False))
    assert result.valid is False
    assert result.reason_code == "OBSERVATION_EXTERNAL_ORIGIN_REQUIRED"


def test_external_attestation_remains_distinct_from_direct_observation():
    attestation = _source(EpistemicSourceType.EXTERNAL_ATTESTATION, external=True)
    assert validate_source_record(attestation).valid is True
    assert attestation.source_type is EpistemicSourceType.EXTERNAL_ATTESTATION
    reclassified = observation_reclassification_allowed(attestation)
    assert reclassified.valid is False
    assert reclassified.reason_code == "NEW_OBSERVATION_REQUIRED"


def test_new_observation_does_not_rewrite_old_derivational_provenance():
    derivation = _source(EpistemicSourceType.DERIVATION)
    observation = _source(EpistemicSourceType.OBSERVATION, external=True, source_id="OBS-NEW")
    result = observation_reclassification_allowed(
        derivation,
        supporting_observation=observation,
    )
    assert result.valid is False
    assert result.reason_code == "PRESERVE_ORIGINAL_SOURCE_TYPE"
    assert derivation.source_type is EpistemicSourceType.DERIVATION


def test_source_classification_alone_cannot_upgrade_unknown_assurance():
    observation = _source(EpistemicSourceType.OBSERVATION, external=True)
    assert validate_source_record(observation).valid is True

    rule = RuleBinding("generic-rule", "1", "generic-authority", "TX", AT)
    context = AssuranceContext(None, "review", "record", "TX", AT)
    source_state = State("E-UNKNOWN", {"applicability": AssuranceState.UNKNOWN}, context, rule)
    target_state = State("E-UNKNOWN:target", {"applicability": AssuranceState.PRESERVED}, context, rule)
    result = evaluate_evidentiary_envelope(
        EvidentiaryEnvelope(
            transition_id="T-SOURCE-TYPE-UNKNOWN",
            source=source_state,
            target=target_state,
            material_properties=frozenset(),
        )
    )
    assert result["state"] == "UNKNOWN"
    assert result["decision"] == "DEFER"
