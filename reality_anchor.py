"""
FAP-Insurance — Reality Anchor
Independent NOAA solar + weather checks.
Cross-validates FAP-Core findings against primary sources.
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from logger import log
from settings import SETTINGS


class RealityAnchor:
    """Performs independent reality checks on claim data."""

    def __init__(self, http: httpx.AsyncClient):
        self._http = http

    async def check_solar(self, claim_time: datetime) -> Dict[str, Any]:
        """Fetch GOES X-ray flux from NOAA SWPC. Independent of FAP-Core."""
        try:
            resp = await self._http.get(
                SETTINGS.NOAA_SWPC_URL,
                timeout=SETTINGS.HTTP_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, list) or len(data) == 0:
                return {"available": False, "reason": "empty_swpc_response"}

            latest = data[-1]
            flux = float(latest.get("flux", 0.0))

            # Normalize to 0-1 confidence (typical range 1e-9 to 1e-3)
            score = min(1.0, max(0.0, (math.log10(flux + 1e-10) + 9) / 6))

            return {
                "available": True,
                "flux": flux,
                "energy": latest.get("energy", ""),
                "time_tag": latest.get("time_tag", ""),
                "confidence": round(score, 4),
                "source": "NOAA_SWPC_DIRECT",
            }
        except Exception as exc:
            log.warning("reality.solar_failed", error=str(exc))
            return {"available": False, "reason": str(exc)}

    async def check_weather(self, lat: float, lon: float) -> Dict[str, Any]:
        """Fetch weather from Open-Meteo. Independent of FAP-Core."""
        try:
            url = (
                f"{SETTINGS.OPEN_METEO_URL}"
                f"?latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
                f"&temperature_unit=fahrenheit&wind_speed_unit=mph"
            )
            resp = await self._http.get(url, timeout=SETTINGS.HTTP_TIMEOUT_SECONDS)
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current", {})

            return {
                "available": True,
                "temperature_f": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "wind_speed_mph": current.get("wind_speed_10m"),
                "weather_code": current.get("weather_code"),
                "source": "Open-Meteo_DIRECT",
            }
        except Exception as exc:
            log.warning("reality.weather_failed", error=str(exc))
            return {"available": False, "reason": str(exc)}

    async def cross_validate(
        self,
        claim_time: datetime,
        lat: float,
        lon: float,
        fap_components: Dict[str, float],
    ) -> Dict[str, Any]:
        """Run independent checks and flag discrepancies with FAP-Core."""
        solar, weather = await asyncio.gather(
            self.check_solar(claim_time),
            self.check_weather(lat, lon),
            return_exceptions=True,
        )

        if isinstance(solar, Exception):
            solar = {"available": False, "reason": str(solar)}
        if isinstance(weather, Exception):
            weather = {"available": False, "reason": str(weather)}

        discrepancies: list[str] = []

        # Cross-check: if FAP-Core claims high solar but we see zero flux
        fap_solar = fap_components.get("solar", 0.0)
        if solar.get("available") and solar.get("confidence", 0.0) < 0.1 and fap_solar > 0.8:
            discrepancies.append(
                f"FAP-Core solar={fap_solar:.2f} but NOAA shows near-zero flux. "
                "Possible data manipulation or stale FAP-Core cache."
            )

        # Cross-check: if FAP-Core claims high weather but we cannot verify
        fap_weather = fap_components.get("weather", 0.0)
        if not weather.get("available") and fap_weather > 0.7:
            discrepancies.append(
                f"FAP-Core weather={fap_weather:.2f} but independent weather oracle failed. "
                "Confidence should be reduced."
            )

        return {
            "independent_solar": solar,
            "independent_weather": weather,
            "discrepancies": discrepancies,
            "cross_validated": len(discrepancies) == 0,
        }
