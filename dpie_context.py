"""Request-local DPIE context shared by the API, audit ledger, and response model.

ContextVar keeps the assurance boundary isolated per request/task; it is not a
policy store and contains no authentication state.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RequestAssuranceContext:
    evidence_id: Optional[str]
    source_purpose: str
    source_scope: Optional[str]
    source_jurisdiction: Optional[str]
    source_at: Optional[datetime]
    target_purpose: str
    target_scope: Optional[str]
    target_jurisdiction: Optional[str]
    target_at: Optional[datetime]
    rule_id: str
    rule_version: str
    rule_authority: str
    consequence: str
    preservation_proof: Optional[Dict[str, Any]] = None


_current: ContextVar[Optional[RequestAssuranceContext]] = ContextVar("dpie_assurance_context", default=None)


def set_context(context: RequestAssuranceContext) -> None:
    _current.set(context)


def get_context() -> Optional[RequestAssuranceContext]:
    return _current.get()


def clear_context() -> None:
    _current.set(None)
