"""
FAP-Insurance — Solar & Weather Oracles
TTL-cached NOAA SWPC + NWS weather. Open-Meteo fallback chain.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from cachetools import TTLCache

from config import SETTINGS
from logger import log

# ── In-memory caches ────────────────────────────────────────
_solar_cache: TTLCache = TTLCache(maxsize=128, ttl=SETTINGS.SOLAR_CACHE_TTL_SECONDS)
_weather_cache: TTLCache = TTLCache(maxsize=256, ttl=SETTINGS.WEATHER_CACHE_TTL_SECONDS)

# ── Shared HTTP client (module-level, lifespan-managed in api.py) ──
_http: Optional[httpx.AsyncClient] = None


def set_http_client(client: httpx.AsyncClient) -> None:
    global _http
    _http = client


# ─────────────────────────────────────────────────────────────
# Solar Oracle — NOAA SWPC GOES X-ray
# ─────────────────────────────────────────────────────────────

async def fetch_solar_flux() -> Dict[str, Any]:
    """Fetch latest GOES X-ray flux from NOAA SWPC. Cached 60s."""
    cache_key = "solar:latest"
    if cache_key in _solar_cache:
        log.debug("solar.cache_hit")
        return _solar_cache[cache_key]

    if _http is None:
        raise RuntimeError("HTTP client not initialized.")

    try:
        resp = await _http.get(
            SETTINGS.NOAA_SWPC_URL,
            timeout=SETTINGS.HTTP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, list) or len(data) == 0:
            raise ValueError("Empty or malformed SWPC response.")

        latest = data[-1]
        result = {
            "flux": latest.get("flux", 0.0),
            "energy": latest.get("energy", ""),
            "time_tag": latest.get("time_tag", ""),
            "source": "NOAA_SWPC",
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        _solar_cache[cache_key] = result
        log.info("solar.fetch_ok", flux=result["flux"])
        return result

    except Exception as exc:
        log.error("solar.fetch_failed", error=str(exc))
        raise


def solar_confidence(claim_time: datetime, solar_data: Dict[str, Any]) -> float:
    """Score how well claim_time aligns with recorded solar flux.
    Hardcoded heuristic: if we have flux data, return high confidence.
    Future: match exact minute-level flux."""
    flux = solar_data.get("flux", 0.0)
    if flux == 0.0:
        return 0.0
    # Normalize flux to 0–1 (typical GOES range 1e-9 to 1e-3)
    import math
    score = min(1.0, max(0.0, math.log10(flux + 1e-10) + 9) / 6)
    return round(score, 4)


# ─────────────────────────────────────────────────────────────
# Weather Oracle — NWS (US) → Open-Meteo (global fallback)
# ─────────────────────────────────────────────────────────────

def _weather_cache_key(lat: float, lon: float) -> str:
    # Bucket to ~0.01 degree to avoid cache fragmentation
    return f"weather:{round(lat, 2)}:{round(lon, 2)}"


async def fetch_weather(lat: float, lon: float) -> Dict[str, Any]:
    """Fetch weather for lat/lon. NWS first (US), Open-Meteo fallback."""
    cache_key = _weather_cache_key(lat, lon)
    if cache_key in _weather_cache:
        log.debug("weather.cache_hit", lat=lat, lon=lon)
        return _weather_cache[cache_key]

    if _http is None:
        raise RuntimeError("HTTP client not initialized.")

    # ── Attempt 1: NOAA NWS (US-only, free, keyless) ────────
    try:
        result = await _fetch_nws_weather(lat, lon)
        _weather_cache[cache_key] = result
        log.info("weather.nws_ok", lat=lat, lon=lon)
        return result
    except Exception as exc:
        log.warning("weather.nws_failed", error=str(exc), lat=lat, lon=lon)

    # ── Attempt 2: Open-Meteo (global, free, keyless) ───────
    try:
        result = await _fetch_open_meteo_weather(lat, lon)
        _weather_cache[cache_key] = result
        log.info("weather.openmeteo_ok", lat=lat, lon=lon)
        return result
    except Exception as exc:
        log.error("weather.openmeteo_failed", error=str(exc), lat=lat, lon=lon)
        raise RuntimeError(f"All weather oracles failed for ({lat}, {lon}).")


async def _fetch_nws_weather(lat: float, lon: float) -> Dict[str, Any]:
    """NOAA NWS points endpoint."""
    points_url = f"{SETTINGS.NOAA_NWS_BASE}/points/{lat:.4f},{lon:.4f}"
    resp = await _http.get(points_url, timeout=SETTINGS.HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    points = resp.json()
    forecast_url = points["properties"]["forecast"]

    forecast_resp = await _http.get(forecast_url, timeout=SETTINGS.HTTP_TIMEOUT_SECONDS)
    forecast_resp.raise_for_status()
    forecast = forecast_resp.json()
    period = forecast["properties"]["periods"][0]

    return {
        "temperature_f": period.get("temperature"),
        "temperature_unit": period.get("temperatureUnit", "F"),
        "humidity": None,  # NWS forecast lacks humidity; Open-Meteo has it
        "wind_speed": period.get("windSpeed"),
        "short_forecast": period.get("shortForecast"),
        "source": "NOAA_NWS",
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }


async def _fetch_open_meteo_weather(lat: float, lon: float) -> Dict[str, Any]:
    """Open-Meteo current weather."""
    url = (
        f"{SETTINGS.OPEN_METEO_URL}"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        f"&temperature_unit=fahrenheit&wind_speed_unit=mph"
    )
    resp = await _http.get(url, timeout=SETTINGS.HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    current = data.get("current", {})

    return {
        "temperature_f": current.get("temperature_2m"),
        "temperature_unit": "F",
        "humidity": current.get("relative_humidity_2m"),
        "wind_speed": f"{current.get('wind_speed_10m', 0)} mph",
        "short_forecast": _open_meteo_code_to_text(current.get("weather_code")),
        "source": "Open-Meteo",
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }


def _open_meteo_code_to_text(code: Optional[int]) -> str:
    mapping = {
        0: "Clear sky",
        1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
    }
    return mapping.get(code, "Unknown")


def weather_confidence(
    claim_temp_f: Optional[float],
    claim_conditions: Optional[str],
    weather_data: Dict[str, Any],
) -> float:
    """Hardcoded heuristic: if we fetched weather data, return baseline confidence.
    Future: compare claim_temp_f against recorded temperature."""
    if weather_data.get("temperature_f") is None:
        return 0.0
    # Baseline: having any weather data is worth 0.5; exact match would be 1.0
    return 0.5
