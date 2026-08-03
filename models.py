"""
FAP-Insurance — Request / Response Models
Pydantic v2. Validators. OpenAPI examples.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ─────────────────────────────────────────────────────────────
# Enums as Literals (Pydantic-friendly, no external enum dep)
# ─────────────────────────────────────────────────────────────

VerdictStatus = Literal["STRICT", "PROBABLE", "SUSPICIOUS", "QUARANTINE"]


# ─────────────────────────────────────────────────────────────
# Request
# ─────────────────────────────────────────────────────────────

class VerifyClaimRequest(BaseModel):
    """Inbound claim-verification request."""

    # ── Core identifiers ─────────────────────────────────────
    claim_id: str = Field(
        ...,
        description="Unique claim identifier assigned by the insurer.",
        json_schema_extra={"examples": ["CLM-2026-004892"]},
    )

    # ── Media ────────────────────────────────────────────────
    media_url: Optional[str] = Field(
        default=None,
        description="Publicly accessible URL to the evidence media.",
        json_schema_extra={"examples": ["https://cdn.insurer.com/evidence/abc123.jpg"]},
    )
    media_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 hex digest of the media file (64 characters).",
        json_schema_extra={
            "examples": ["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"]
        },
    )

    # ── Geo / Time ───────────────────────────────────────────
    lat: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="Claim latitude in decimal degrees.",
        json_schema_extra={"examples": [29.53]},
    )
    lon: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Claim longitude in decimal degrees.",
        json_schema_extra={"examples": [-98.46]},
    )
    timestamp_claimed: datetime = Field(
        ...,
        description="UTC datetime when the claim event allegedly occurred.",
        json_schema_extra={"examples": ["2026-07-13T22:45:00Z"]},
    )

    # ── Device ───────────────────────────────────────────────
    device_model: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Device model string.",
        json_schema_extra={"examples": ["iPhone15,2"]},
    )
    device_manufacturer: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Device manufacturer.",
        json_schema_extra={"examples": ["Apple"]},
    )
    device_os: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Operating system and version.",
        json_schema_extra={"examples": ["iOS 18.4"]},
    )
    enrollment_id: Optional[str] = Field(
        default=None,
        description="Pre-registered device enrollment ID.",
        json_schema_extra={"examples": ["ENR-7a3f9e2d"]},
    )

    # ── Witnesses ────────────────────────────────────────────
    witness_ids: List[str] = Field(
        default_factory=list,
        description="List of witness enrollment IDs (max 20).",
        json_schema_extra={"examples": [["WIT-001", "WIT-002"]]},
    )

    # ── Insurance metadata ───────────────────────────────────
    policy_number: Optional[str] = Field(
        default=None,
        description="Insurance policy number.",
        json_schema_extra={"examples": ["POL-2026-TX-88421"]},
    )
    adjuster_notes: Optional[str] = Field(
        default=None,
        max_length=4000,
        description="Free-text notes from the assigned adjuster.",
        json_schema_extra={"examples": ["Front-end collision, claimant uninjured."]},
    )

    # ═════════════════════════════════════════════════════════
    # Field Validators
    # ═════════════════════════════════════════════════════════

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
        if len(v) != 64:
            raise ValueError("media_hash must be exactly 64 hexadecimal characters.")
        if not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError("media_hash must contain only hexadecimal characters (0-9, a-f).")
        return v

    @field_validator("timestamp_claimed")
    @classmethod
    def _validate_timestamp(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if v > now + timedelta(seconds=60):
            raise ValueError("timestamp_claimed cannot be in the future.")
        return v

    @field_validator("witness_ids")
    @classmethod
    def _validate_witness_ids(cls, v: List[str]) -> List[str]:
        if len(v) > 20:
            raise ValueError("A maximum of 20 witness IDs is allowed.")
        cleaned: List[str] = []
        for idx, wid in enumerate(v):
            stripped = wid.strip()
            if not stripped:
                raise ValueError(f"witness_ids[{idx}] is blank or whitespace-only.")
            cleaned.append(stripped)
        return cleaned

    @model_validator(mode="after")
    def _check_media_consistency(self) -> "VerifyClaimRequest":
        """Cross-field: if media_url exists without hash, we allow it
        but downstream will flag media_hash_verified as None."""
        return self


# ─────────────────────────────────────────────────────────────
# Response
# ─────────────────────────────────────────────────────────────

class VerifyClaimResponse(BaseModel):
    """Outbound claim-verification result."""

    claim_id: str = Field(..., description="Echo of the inbound claim_id.")
    status: VerdictStatus = Field(
        ...,
        description="High-level verdict.",
        json_schema_extra={"examples": ["STRICT"]},
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Aggregate confidence score (0.0 – 1.0).",
        json_schema_extra={"examples": [0.96]},
    )
    solar_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Solar-oracle confidence component.",
    )
    weather_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Weather-oracle confidence component.",
    )
    device_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Device-signature confidence component.",
    )
    witness_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Witness-consensus confidence component.",
    )
    gps_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="GPS-plausibility confidence component.",
    )
    media_hash_verified: Optional[bool] = Field(
        default=None,
        description="True if downloaded media hash matches provided media_hash.",
    )
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when verification completed.",
    )
    request_id: str = Field(
        ...,
        description="Unique trace ID for this verification request.",
        json_schema_extra={"examples": ["req-7f3a9e2d-8842-4b91-b3c7-1e8d6f5a2c09"]},
    )


# ─────────────────────────────────────────────────────────────
# Error Response (for OpenAPI docs)
# ─────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standardized error envelope."""

    error: str = Field(..., description="Error type code.")
    detail: str = Field(..., description="Human-readable explanation.")
    request_id: Optional[str] = Field(default=None)
    field: Optional[str] = Field(default=None)
