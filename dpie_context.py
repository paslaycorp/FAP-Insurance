"""Request-local DPIE context shared by the API, audit ledger, and response model.

ContextVar keeps the assurance boundary isolated per request/task; it is not a
policy store and contains no authentication state.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from epm import EvidenceAvailability


@dataclass(frozen=True)
class RequestAssuranceContext:
    evidence_id: str | None
    source_purpose: str
    source_scope: str | None
    source_jurisdiction: str | None
    source_at: datetime | None
    target_purpose: str
    target_scope: str | None
    target_jurisdiction: str | None
    target_at: datetime | None
    rule_id: str
    rule_version: str
    rule_authority: str
    consequence: str
    preservation_proof: dict[str, Any] | None = None
    evidence_availability: EvidenceAvailability | None = None
    require_trusted_availability: bool = False
    event_time: datetime | None = None


_current: ContextVar[RequestAssuranceContext | None] = ContextVar("dpie_assurance_context", default=None)


def set_context(context: RequestAssuranceContext) -> None:
    _current.set(context)


def get_context() -> RequestAssuranceContext | None:
    return _current.get()


def clear_context() -> None:
    _current.set(None)
