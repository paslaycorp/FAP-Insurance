"""FAP-Insurance request/response models.

The response fields mirror the live /verify implementation. DPIE fields are
optional so existing clients remain valid while downstream assurance context
can be supplied explicitly.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

VerdictStatus = Literal["STRICT", "PROBABLE", "SUSPICIOUS", "QUARANTINE"]


class VerifyClaimRequest(BaseModel):
    claim_id: str = Field(..., description="Unique claim identifier assigned by the insurer.")
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

    # DPIE downstream context. Defaults preserve the existing /verify behavior:
    # no material downstream boundary is declared unless the caller changes it.
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

    @field_validator("timestamp_claimed")
    @classmethod
    def _validate_timestamp(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v > datetime.now(timezone.utc) + timedelta(seconds=60):
            raise ValueError("timestamp_claimed cannot be in the future.")
        return v

    @field_validator("downstream_at")
    @classmethod
    def _normalize_downstream_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("witness_ids")
    @classmethod
    def _validate_witness_ids(cls, v: List[str]) -> List[str]:
        if len(v) > 20:
            raise ValueError("A maximum of 20 witness IDs is allowed.")
        return [wid.strip() for wid in v]

    @model_validator(mode="after")
    def _check_witness_ids(self) -> "VerifyClaimRequest":
        if any(not wid for wid in self.witness_ids):
            raise ValueError("witness_ids cannot contain blank values.")
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

    # DPIE determination is deliberately separate from FAP verdict.
    dpie_transition_id: Optional[str] = None
    dpie_property: Optional[str] = None
    dpie_state: Optional[str] = None
    dpie_decision: Optional[str] = None
    dpie_failure: Optional[str] = None
    dpie_reason: Optional[str] = None
    dpie_fail_closed: Optional[bool] = None

    # Legacy contract fields retained as optional aliases for older clients.
    status: Optional[VerdictStatus] = None
    solar_confidence: Optional[float] = None
    weather_confidence: Optional[float] = None
    device_confidence: Optional[float] = None
    witness_confidence: Optional[float] = None
    gps_confidence: Optional[float] = None
    media_hash_verified: Optional[bool] = None
    processed_at: Optional[datetime] = None
    request_id: Optional[str] = None


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
