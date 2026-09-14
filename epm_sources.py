"""Epistemic source typing for EPM vNext.

Source type records how information entered the system. It does not establish
truth, assurance, applicability, or authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class EpistemicSourceType(str, Enum):
    OBSERVATION = "OBSERVATION"
    DERIVATION = "DERIVATION"
    DISCRIMINATOR = "DISCRIMINATOR"
    CONSTRAINT = "CONSTRAINT"
    ASSERTION = "ASSERTION"
    EXTERNAL_ATTESTATION = "EXTERNAL_ATTESTATION"
    COMPUTATIONAL_DISCOVERY = "COMPUTATIONAL_DISCOVERY"


@dataclass(frozen=True)
class EpistemicSourceRecord:
    source_id: str
    source_type: EpistemicSourceType
    producer: str
    provenance_refs: Tuple[str, ...]
    input_refs: Tuple[str, ...] = ()
    external_origin: bool = False


@dataclass(frozen=True)
class SourceTypingResult:
    valid: bool
    reason_code: str
    reason: str


def validate_source_record(record: EpistemicSourceRecord) -> SourceTypingResult:
    if not record.source_id.strip():
        return SourceTypingResult(False, "SOURCE_ID_REQUIRED", "Source identity is required.")
    if not record.producer.strip():
        return SourceTypingResult(False, "PRODUCER_REQUIRED", "Source producer is required.")
    if not record.provenance_refs or any(not ref.strip() for ref in record.provenance_refs):
        return SourceTypingResult(False, "PROVENANCE_REQUIRED", "Typed sources require non-empty provenance references.")
    if record.source_type is EpistemicSourceType.OBSERVATION and not record.external_origin:
        return SourceTypingResult(False, "OBSERVATION_EXTERNAL_ORIGIN_REQUIRED", "Observation source type requires an external origin outside the current computation boundary.")
    if record.source_type is EpistemicSourceType.EXTERNAL_ATTESTATION and not record.external_origin:
        return SourceTypingResult(False, "ATTESTATION_EXTERNAL_ORIGIN_REQUIRED", "External attestation source type requires an external origin.")
    return SourceTypingResult(True, "SOURCE_TYPE_VALID", "Source record preserves its declared origin type and provenance.")


def observation_reclassification_allowed(
    source: EpistemicSourceRecord,
    *,
    supporting_observation: Optional[EpistemicSourceRecord] = None,
) -> SourceTypingResult:
    """Reject relabeling internal outputs as observations without new observation.

    The supporting observation is new evidence; it does not retroactively turn
    the old derivation/discriminator/computation into an observation. A caller
    may use the new observation to establish a new evidentiary state instead.
    """
    current = validate_source_record(source)
    if not current.valid:
        return current
    if source.source_type is EpistemicSourceType.OBSERVATION:
        return SourceTypingResult(True, "ALREADY_OBSERVATION", "Source is already a valid observation record.")
    if supporting_observation is None:
        return SourceTypingResult(False, "NEW_OBSERVATION_REQUIRED", "Internal computation, derivation, assertion, constraint, or discriminator output cannot be relabeled as observation without new external observational evidence.")
    support = validate_source_record(supporting_observation)
    if not support.valid or supporting_observation.source_type is not EpistemicSourceType.OBSERVATION:
        return SourceTypingResult(False, "VALID_OBSERVATION_REQUIRED", "Supporting evidence must itself be a valid externally originated observation.")
    return SourceTypingResult(False, "PRESERVE_ORIGINAL_SOURCE_TYPE", "New observation may support a new evidentiary state, but it does not change the provenance type of the pre-existing source record.")


def computational_output_type() -> EpistemicSourceType:
    """Canonical type for newly discovered output produced only by computation."""
    return EpistemicSourceType.COMPUTATIONAL_DISCOVERY
