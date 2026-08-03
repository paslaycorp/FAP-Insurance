"""
FAP-Insurance — Evidence Fusion Engine

Bayesian-inspired fusion of independent oracle observations.
Each observation is a witness. The engine weighs them,
detects discrepancies, and produces a defensible confidence score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from evidence import OracleObservation


@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    confidence: float          # 0.0–1.0
    verdict: str               # STRICT | PROBABLE | SUSPICIOUS | QUARANTINE
    reason_codes: List[str]    # Human-readable explanations
    observations_used: int
    observations_failed: int
    discrepancies: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence": self.confidence,
            "verdict": self.verdict,
            "reason_codes": self.reason_codes,
            "observations_used": self.observations_used,
            "observations_failed": self.observations_failed,
            "discrepancies": self.discrepancies,
        }


class EvidenceFusionEngine:
    """
    Fuses independent oracle observations into a single confidence score.

    Algorithm:
      1. Separate OK observations from FAILED/DEGRADED/DISCREPANCY
      2. OK observations: confidence = 1 - product(1 - c_i)
      3. Penalty: -0.15 per FAILED, -0.10 per DEGRADED, -0.20 per DISCREPANCY
      4. Verdict thresholds: 0.90 STRICT, 0.70 PROBABLE, 0.40 SUSPICIOUS, else QUARANTINE
      5. Generate reason codes for every decision
    """

    THRESHOLD_STRICT: float = 0.90
    THRESHOLD_PROBABLE: float = 0.70
    THRESHOLD_SUSPICIOUS: float = 0.40

    PENALTY_FAILED: float = 0.15
    PENALTY_DEGRADED: float = 0.10
    PENALTY_DISCREPANCY: float = 0.20

    def evaluate(self, observations: List[OracleObservation]) -> ConfidenceResult:
        ok_obs = [o for o in observations if o.status == "OK"]
        failed_obs = [o for o in observations if o.status == "FAILED"]
        degraded_obs = [o for o in observations if o.status == "DEGRADED"]
        discrepancy_obs = [o for o in observations if o.status == "DISCREPANCY"]

        reason_codes: List[str] = []
        discrepancies: List[str] = []

        # ── Independent evidence fusion ──────────────────────
        if not ok_obs:
            confidence = 0.0
            reason_codes.append("No oracle observations returned OK status.")
        else:
            product = 1.0
            for obs in ok_obs:
                product *= (1.0 - obs.confidence)
            confidence = 1.0 - product
            reason_codes.append(
                f"Fused {len(ok_obs)} independent observations. "
                f"Base confidence: {confidence:.4f}"
            )

        # ── Penalties ────────────────────────────────────────
        penalty = (
            self.PENALTY_FAILED * len(failed_obs)
            + self.PENALTY_DEGRADED * len(degraded_obs)
            + self.PENALTY_DISCREPANCY * len(discrepancy_obs)
        )
        confidence = max(0.0, confidence - penalty)

        for obs in failed_obs:
            reason_codes.append(f"[{obs.oracle_type}] FAILED: {obs.discrepancy_note or 'No data'}")
        for obs in degraded_obs:
            reason_codes.append(f"[{obs.oracle_type}] DEGRADED: {obs.discrepancy_note or 'Reduced confidence'}")
        for obs in discrepancy_obs:
            discrepancies.append(f"[{obs.oracle_type}] {obs.discrepancy_note or 'Discrepancy detected'}")
            reason_codes.append(f"[{obs.oracle_type}] DISCREPANCY: {obs.discrepancy_note or 'Cross-check failed'}")

        # ── Verdict ──────────────────────────────────────────
        if confidence >= self.THRESHOLD_STRICT and not discrepancy_obs:
            verdict = "STRICT"
        elif confidence >= self.THRESHOLD_PROBABLE:
            verdict = "PROBABLE"
        elif confidence >= self.THRESHOLD_SUSPICIOUS:
            verdict = "SUSPICIOUS"
        else:
            verdict = "QUARANTINE"

        # Override: any discrepancy forces at least SUSPICIOUS
        if discrepancy_obs and verdict == "STRICT":
            verdict = "SUSPICIOUS"
            reason_codes.append("Verdict downgraded from STRICT to SUSPICIOUS due to cross-validation discrepancies.")

        return ConfidenceResult(
            confidence=round(confidence, 4),
            verdict=verdict,
            reason_codes=reason_codes,
            observations_used=len(ok_obs),
            observations_failed=len(failed_obs) + len(degraded_obs) + len(discrepancy_obs),
            discrepancies=discrepancies,
        )
