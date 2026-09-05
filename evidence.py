"""FAP Evidence Envelope with forensic audit serialization."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OracleObservation(BaseModel):
    oracle_type: str = Field(...)
    source: str = Field(...)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = Field(..., ge=0.0, le=1.0)
    raw_value: Optional[Any] = None
    status: str = "OK"
    discrepancy_note: Optional[str] = None

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


class EvidenceEnvelope(BaseModel):
    evidence_id: str
    media_hash: str
    c2pa_present: bool = False
    c2pa_valid: Optional[bool] = None
    c2pa_manifest_hash: Optional[str] = None
    c2pa_signer: Optional[str] = None
    c2pa_claims: List[str] = Field(default_factory=list)
    capture_time: datetime
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    device_id: Optional[str] = None
    observations: List[OracleObservation] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    verdict: str = "UNKNOWN"
    audit_record_hash: Optional[str] = None
    fap_core_response: Optional[Dict[str, Any]] = None

    def add_observation(self, obs: OracleObservation) -> "EvidenceEnvelope":
        self.observations.append(obs)
        self._recalculate_confidence()
        return self

    def _recalculate_confidence(self) -> None:
        ok_obs = [o for o in self.observations if o.status == "OK"]
        failed_obs = [o for o in self.observations if o.status in ("FAILED", "DISCREPANCY")]
        if not ok_obs:
            self.confidence_score = 0.0
            return
        product = 1.0
        for obs in ok_obs:
            product *= (1.0 - obs.confidence)
        self.confidence_score = max(0.0, min(1.0, 1.0 - product - 0.15 * len(failed_obs)))

    def compute_verdict(self) -> str:
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
        """Serialize FAP evidence plus the DPIE determination into the same ledger record."""
        payload: Dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "media_hash": self.media_hash,
            "c2pa_present": self.c2pa_present,
            "c2pa_valid": self.c2pa_valid,
            "c2pa_manifest_hash": self.c2pa_manifest_hash,
            "c2pa_signer": self.c2pa_signer,
            "c2pa_claims": list(self.c2pa_claims),
            "capture_time": self.capture_time.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "device_id": self.device_id,
            "observations": [o.to_dict() for o in self.observations],
            "confidence_score": self.confidence_score,
            "verdict": self.verdict,
        }
        try:
            from dpie_context import get_context
            from dpie_runtime import assess_request_context
            context = get_context()
            if context is not None:
                determination = assess_request_context(
                    evidence_id=self.evidence_id,
                    verification={"verdict": self.verdict},
                    context=context,
                )
                payload["dpie"] = {
                    "transition_id": determination["transition_id"],
                    "property": determination["property"],
                    "state": determination["state"],
                    "decision": determination["decision"],
                    "failure": determination["failure"],
                    "reason": determination["reason"],
                    "rule_id": determination["rule_id"],
                    "rule_version": determination["rule_version"],
                    "source_evidence_id": self.evidence_id,
                    "fail_closed": determination["fail_closed"],
                    "source_context": {
                        "purpose": context.source_purpose,
                        "scope": context.source_scope,
                        "jurisdiction": context.source_jurisdiction,
                        "at": context.source_at.isoformat() if context.source_at else None,
                    },
                    "target_context": {
                        "purpose": context.target_purpose,
                        "scope": context.target_scope,
                        "jurisdiction": context.target_jurisdiction,
                        "at": context.target_at.isoformat() if context.target_at else None,
                    },
                    "rule_authority": context.rule_authority,
                    "consequence": context.consequence,
                }
        except Exception:
            # Ledger serialization must not invent assurance. The failure is
            # intentionally omitted here; the endpoint/model path still
            # exposes the runtime exception rather than silently authorizing.
            raise
        return payload

    def discrepancy_report(self) -> List[str]:
        return [f"[{o.oracle_type}] {o.discrepancy_note}" for o in self.observations if o.discrepancy_note]
