"""Minimal adjuster report renderer used by the existing API/audit contract."""
from __future__ import annotations

from html import escape
from typing import Any, Dict, Optional


class AdjusterReport:
    def __init__(self, claim_id: str, policy_number: Optional[str], adjuster_notes: Optional[str], fap_result: Dict[str, Any], request_data: Dict[str, Any]):
        self.claim_id = claim_id
        self.policy_number = policy_number
        self.adjuster_notes = adjuster_notes
        self.fap_result = fap_result
        self.request_data = request_data

    def to_html(self) -> str:
        verdict = escape(str(self.fap_result.get("verdict", "UNKNOWN")))
        return (
            "<!doctype html><html><body>"
            f"<h1>FAP-Insurance Verification Report</h1><p>Claim: {escape(self.claim_id)}</p>"
            f"<p>Policy: {escape(str(self.policy_number or ''))}</p><p>Verdict: {verdict}</p>"
            f"<p>{escape(str(self.adjuster_notes or ''))}</p>"
            "</body></html>"
        )
