"""FAP-Insurance request/response models with explicit DPIE context."""
from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from dpie_context import RequestAssuranceContext, set_context

VerdictStatus = Literal["STRICT", "PROBABLE", "SUSPICIOUS", "QUARANTINE"]


class VerifyClaimRequest(BaseModel):
    claim_id: str = Field(...)
    media_url: Optional[str] = None
    media_hash: Optional[str] = None
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    timestamp_claimed: datetime
    device_model: str = Field(..., min_length=1, max_length=128)
    device_manufacturer: str = Field(..., min_length=1, max_length=128)
    device_os: str = Field(..., min_length=1, max_length=128)
    enrollment_id: Optional[str] = None
    witness_ids: List[str] = Field(default_factory=list)
    policy_number: Optional[str] = None
    adjuster_notes: Optional[str] = Field(default=None, max_length=4000)

    downstream_purpose: Optional[str] = None
    downstream_scope: Optional[str] = None
    downstream_jurisdiction: Optional[str] = None
    downstream_at: Optional[datetime] = None
    downstream_rule_id: Optional[str] = None
    downstream_rule_version: Optional[str] = None
    downstream_rule_authority: Optional[str] = None
    downstream_consequence: Literal["standard", "critical"] = "standard"
    preservation_proof: Optional[Dict[str, Any]] = None

    @field_validator("claim_id")
    @classmethod
    def _validate_claim_id(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 6:
            raise ValueError("claim_id must be at least 6 characters after stripping whitespace.")
        return v

    @field_validator("media_hash")
    @classmethod
    def _validate_media_hash(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if len(v) != 64 or not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError("media_hash must be exactly 64 hexadecimal characters.")
        return v

    @field_validator("timestamp_claimed", "downstream_at")
    @classmethod
    def _normalize_datetime(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("timestamp_claimed")
    @classmethod
    def _not_future(cls, v: datetime) -> datetime:
        if v > datetime.now(timezone.utc) + timedelta(seconds=60):
            raise ValueError("timestamp_claimed cannot be in the future.")
        return v

    @field_validator("witness_ids")
    @classmethod
    def _validate_witness_ids(cls, v: List[str]) -> List[str]:
        if len(v) > 20 or any(not x.strip() for x in v):
            raise ValueError("witness_ids must contain 0-20 non-blank values.")
        return [x.strip() for x in v]

    @model_validator(mode="after")
    def _set_dpie_context(self) -> "VerifyClaimRequest":
        source_purpose = "claim-verification"
        target_purpose = self.downstream_purpose or source_purpose
        source_scope = "claim"
        target_scope = self.downstream_scope or source_scope
        source_jurisdiction = "TX"
        target_jurisdiction = self.downstream_jurisdiction or source_jurisdiction
        source_at = self.timestamp_claimed
        target_at = self.downstream_at or source_at
        set_context(RequestAssuranceContext(
            evidence_id=None,
            source_purpose=source_purpose,
            source_scope=source_scope,
            source_jurisdiction=source_jurisdiction,
            source_at=source_at,
            target_purpose=target_purpose,
            target_scope=target_scope,
            target_jurisdiction=target_jurisdiction,
            target_at=target_at,
            rule_id=self.downstream_rule_id or "carrier-default",
            rule_version=self.downstream_rule_version or "1",
            rule_authority=self.downstream_rule_authority or "carrier-authority",
            consequence=self.downstream_consequence,
            preservation_proof=self.preservation_proof,
        ))
        return self


class VerifyClaimResponse(BaseModel):
    claim_id: str
    verification_id: str = "unknown"
    verdict: VerdictStatus
    verdict_label: str
    score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    components: Dict[str, Any] = Field(default_factory=dict)
    solar_flux_at_time: Optional[float] = None
    weather_match: Optional[float] = None
    device_enrolled: bool = False
    witness_count: int = Field(default=0, ge=0)
    processing_time_ms: int = Field(default=0, ge=0)
    report_url: Optional[str] = None
    recommendation: str
    timestamp_processed: datetime
    dpie_transition_id: Optional[str] = None
    dpie_property: Optional[str] = None
    dpie_state: Optional[str] = None
    dpie_decision: Optional[str] = None
    dpie_failure: Optional[str] = None
    dpie_reason: Optional[str] = None
    dpie_fail_closed: Optional[bool] = None
    status: Optional[VerdictStatus] = None
    solar_confidence: Optional[float] = None
    weather_confidence: Optional[float] = None
    device_confidence: Optional[float] = None
    witness_confidence: Optional[float] = None
    gps_confidence: Optional[float] = None
    media_hash_verified: Optional[bool] = None
    processed_at: Optional[datetime] = None
    request_id: Optional[str] = None

    @model_validator(mode="after")
    def _evaluate_dpie(self) -> "VerifyClaimResponse":
        from dpie_context import get_context
        from dpie_runtime import assess_request_context
        ctx = get_context()
        if ctx is None:
            return self
        result = assess_request_context(
            evidence_id=self.verification_id,
            verification={"verdict": self.verdict},
            context=ctx,
        )
        self.dpie_transition_id = result["transition_id"]
        self.dpie_property = result["property"]
        self.dpie_state = result["state"]
        self.dpie_decision = result["decision"]
        self.dpie_failure = result["failure"]
        self.dpie_reason = result["reason"]
        self.dpie_fail_closed = result["fail_closed"]
        return self


class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: Optional[str] = None
    field: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    fap_core_connected: bool
    version: str
    timestamp: datetime
