"""
FAP-Insurance — Evidence Envelope

FAP-Core sits ABOVE C2PA, not competing with it.
The EvidenceEnvelope is the unified provenance container that:
  · Ingests C2PA manifests (if present)
  · Attaches independent reality observations (solar, weather, device)
  · Produces a single confidence score via Bayesian fusion
  · Writes to the forensic audit ledger

This is the strategic layer that makes FAP-Core defensible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Oracle Observation ─────────────────────────────────────

class OracleObservation(BaseModel):
    """A single independent reality observation."""

    oracle_type: str = Field(..., description="solar | weather | device | location | c2pa | consensus")
    source: str = Field(..., description="NOAA_SWPC | Open-Meteo | FAP-Core | C2PA | DeviceRegistry")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = Field(..., ge=0.0, le=1.0)
    raw_value: Optional[Any] = Field(default=None, description="Raw measurement (flux, temp, etc.)")
    status: str = Field(default="OK", description="OK | DEGRADED | FAILED | DISCREPANCY")
    discrepancy_note: Optional[str] = Field(default=None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "oracle_type": self.oracle_type,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "raw_value": self.raw_value,
            "status": self.status,
            "discrepancy_note": self.discrepancy_note,
        }


# ── Evidence Envelope ──────────────────────────────────────

class EvidenceEnvelope(BaseModel):
    """
    Unified provenance container.

    Flow:
      1. Ingest media + metadata
      2. Extract C2PA manifest (if present)
      3. Run independent oracles (solar, weather, device)
      4. Collect OracleObservations
      5. Fuse into confidence_score
      6. Persist to forensic audit ledger
    """

    evidence_id: str = Field(..., description="FAP-generated evidence envelope ID")
    media_hash: str = Field(..., description="SHA-256 of the media file")

    # ── Provenance layer (C2PA) ────────────────────────────
    c2pa_present: bool = Field(default=False)
    c2pa_valid: Optional[bool] = Field(default=None)
    c2pa_manifest_hash: Optional[str] = Field(default=None)
    c2pa_signer: Optional[str] = Field(default=None)
    c2pa_claims: List[str] = Field(default_factory=list)

    # ── Reality layer ──────────────────────────────────────
    capture_time: datetime
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    device_id: Optional[str] = Field(default=None)

    # ── Oracle observations (the signal layer) ─────────────
    observations: List[OracleObservation] = Field(default_factory=list)

    # ── Consensus ──────────────────────────────────────────
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    verdict: str = Field(default="UNKNOWN")

    # ── Audit linkage ──────────────────────────────────────
    audit_record_hash: Optional[str] = Field(default=None)
    fap_core_response: Optional[Dict[str, Any]] = Field(default=None)

    def add_observation(self, obs: OracleObservation) -> "EvidenceEnvelope":
        self.observations.append(obs)
        self._recalculate_confidence()
        return self

    def _recalculate_confidence(self) -> None:
        """Bayesian-inspired fusion of independent observations.

        Each observation is treated as independent evidence.
        Confidence = 1 - product(1 - c_i) for all OK observations.
        Discrepancies and FAILED observations reduce confidence.
        """
        ok_obs = [o for o in self.observations if o.status == "OK"]
        failed_obs = [o for o in self.observations if o.status in ("FAILED", "DISCREPANCY")]

        if not ok_obs:
            self.confidence_score = 0.0
            return

        # Independent evidence fusion
        product = 1.0
        for obs in ok_obs:
            product *= (1.0 - obs.confidence)
        confidence = 1.0 - product

        # Penalty for failures/discrepancies
        penalty = 0.15 * len(failed_obs)
        self.confidence_score = max(0.0, min(1.0, confidence - penalty))

    def compute_verdict(self) -> str:
        """Map confidence score to verdict thresholds."""
        if self.confidence_score >= 0.90:
            self.verdict = "STRICT"
        elif self.confidence_score >= 0.70:
            self.verdict = "PROBABLE"
        elif self.confidence_score >= 0.40:
            self.verdict = "SUSPICIOUS"
        else:
            self.verdict = "QUARANTINE"
        return self.verdict

    def to_audit_payload(self) -> Dict[str, Any]:
        """Serialize for forensic audit ledger."""
        return {
            "evidence_id": self.evidence_id,
            "media_hash": self.media_hash,
            "c2pa_present": self.c2pa_present,
            "c2pa_valid": self.c2pa_valid,
            "capture_time": self.capture_time.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "device_id": self.device_id,
            "observations": [o.to_dict() for o in self.observations],
            "confidence_score": self.confidence_score,
            "verdict": self.verdict,
        }

    def discrepancy_report(self) -> List[str]:
        """List all discrepancy notes for investor review."""
        return [
            f"[{o.oracle_type}] {o.discrepancy_note}"
            for o in self.observations
            if o.discrepancy_note
        ]
