"""
FAP-Insurance — Solar Oracle (Witness)

Evaluates solar temporal correlation.
A witness, not a judge. Failed lookups become DEGRADED evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from cachetools import TTLCache

from logger import log
from settings import SETTINGS

_solar_cache: TTLCache = TTLCache(maxsize=256, ttl=SETTINGS.SOLAR_CACHE_TTL_SECONDS)


@dataclass(frozen=True, slots=True)
class SolarResult:
    status: str           # OK | DEGRADED | FAILED
    confidence: float     # 0.0–1.0
    flux: Optional[float]
    energy: Optional[str]
    time_tag: Optional[str]
    delta_seconds: Optional[float]
    reason: Optional[str]
    source: str = "NOAA_SWPC"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "flux": self.flux,
            "energy": self.energy,
            "time_tag": self.time_tag,
            "delta_seconds": self.delta_seconds,
            "reason": self.reason,
            "source": self.source,
        }


async def fetch_noaa_swpc() -> List[Dict[str, Any]]:
    cache_key = "swpc:full"
    if cache_key in _solar_cache:
        return _solar_cache[cache_key]

    async with httpx.AsyncClient(timeout=SETTINGS.HTTP_TIMEOUT_SECONDS) as client:
        resp = await client.get(SETTINGS.NOAA_SWPC_URL)
        resp.raise_for_status()
        data = resp.json()

    if not isinstance(data, list):
        raise ValueError("Malformed SWPC response")

    _solar_cache[cache_key] = data
    log.info("solar.noaa_fetched", records=len(data))
    return data


def _find_flux(data: List[Dict[str, Any]], target: datetime, tolerance: float = 120.0) -> Optional[Dict[str, Any]]:
    target_ts = target.astimezone(timezone.utc)
    best = None
    best_delta = float("inf")

    for entry in data:
        time_tag = entry.get("time_tag", "")
        try:
            entry_dt = datetime.strptime(time_tag, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        delta = abs((entry_dt - target_ts).total_seconds())
        if delta < best_delta:
            best_delta = delta
            best = entry

    if best and best_delta <= tolerance:
        return {
            "flux": float(best.get("flux", 0.0)),
            "energy": best.get("energy", ""),
            "time_tag": best.get("time_tag", ""),
            "delta_seconds": best_delta,
        }
    return None


def _flux_to_confidence(flux: float) -> float:
    return min(1.0, max(0.0, (math.log10(flux + 1e-10) + 9) / 6))


async def evaluate_solar_correlation(timestamp_claimed: datetime) -> SolarResult:
    """
    Evaluate solar temporal correlation.
    Never raises. Returns DEGRADED/FAILED on issues.
    """
    # Future timestamp
    if timestamp_claimed > datetime.now(timezone.utc) + __import__("datetime").timedelta(seconds=60):
        return SolarResult(
            status="FAILED",
            confidence=0.0,
            flux=None,
            energy=None,
            time_tag=None,
            delta_seconds=None,
            reason="Claimed timestamp is in the future. Cannot correlate.",
        )

    # Fetch NOAA
    try:
        data = await fetch_noaa_swpc()
    except Exception as exc:
        log.error("solar.fetch_failed", error=str(exc))
        return SolarResult(
            status="DEGRADED",
            confidence=0.0,
            flux=None,
            energy=None,
            time_tag=None,
            delta_seconds=None,
            reason=f"NOAA SWPC unavailable: {exc}",
        )

    if not data:
        return SolarResult(
            status="DEGRADED",
            confidence=0.0,
            flux=None,
            energy=None,
            time_tag=None,
            delta_seconds=None,
            reason="NOAA returned empty dataset.",
        )

    # Find match
    match = _find_flux(data, timestamp_claimed)
    if not match:
        return SolarResult(
            status="DEGRADED",
            confidence=0.0,
            flux=None,
            energy=None,
            time_tag=None,
            delta_seconds=None,
            reason=f"No NOAA record within 120s of {timestamp_claimed.isoformat()}. Timestamp may be fabricated or outside data window.",
        )

    flux = match["flux"]
    confidence = _flux_to_confidence(flux)

    log.info("solar.correlated", time_tag=match["time_tag"], flux=flux, confidence=round(confidence, 4))

    return SolarResult(
        status="OK",
        confidence=round(confidence, 4),
        flux=flux,
        energy=match["energy"],
        time_tag=match["time_tag"],
        delta_seconds=match["delta_seconds"],
        reason=None,
    )
