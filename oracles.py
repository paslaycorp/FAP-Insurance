"""FAP-Insurance external oracle adapters."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from cachetools import TTLCache

from config import SETTINGS
from logger import log

_solar_cache: TTLCache = TTLCache(maxsize=128, ttl=SETTINGS.SOLAR_CACHE_TTL_SECONDS)
_weather_cache: TTLCache = TTLCache(maxsize=256, ttl=SETTINGS.WEATHER_CACHE_TTL_SECONDS)
_http: Optional[httpx.AsyncClient] = None


def set_http_client(client: httpx.AsyncClient) -> None:
    global _http
    _http = client


async def fetch_solar_flux() -> Dict[str, Any]:
    cache_key = "solar:latest"
    if cache_key in _solar_cache:
        return _solar_cache[cache_key]
    if _http is None:
        raise RuntimeError("HTTP client not initialized.")
    try:
        response = await _http.get(SETTINGS.NOAA_SWPC_URL, timeout=SETTINGS.HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or not data:
            raise ValueError("Empty or malformed SWPC response.")
        latest = data[-1]
        result = {"flux": latest.get("flux", 0.0), "energy": latest.get("energy", ""), "time_tag": latest.get("time_tag", ""), "source": "NOAA_SWPC", "cached_at": datetime.now(timezone.utc).isoformat()}
        _solar_cache[cache_key] = result
        return result
    except Exception as exc:
        log.error("solar.fetch_failed", error=str(exc))
        raise


def solar_confidence(claim_time: datetime, solar_data: Dict[str, Any]) -> float:
    import math
    flux = solar_data.get("flux", 0.0)
    if flux == 0.0:
        return 0.0
    return round(min(1.0, max(0.0, math.log10(flux + 1e-10) + 9) / 6), 4)


def _weather_cache_key(lat: float, lon: float) -> str:
    return f"weather:{round(lat, 2)}:{round(lon, 2)}"


async def fetch_weather(lat: float, lon: float) -> Dict[str, Any]:
    cache_key = _weather_cache_key(lat, lon)
    if cache_key in _weather_cache:
        return _weather_cache[cache_key]
    if _http is None:
        raise RuntimeError("HTTP client not initialized.")
    try:
        result = await _fetch_nws_weather(lat, lon)
        _weather_cache[cache_key] = result
        return result
    except Exception as exc:
        log.warning("weather.nws_failed", error=str(exc), lat=lat, lon=lon)
    try:
        result = await _fetch_open_meteo_weather(lat, lon)
        _weather_cache[cache_key] = result
        return result
    except Exception as exc:
        log.error("weather.openmeteo_failed", error=str(exc), lat=lat, lon=lon)
        raise RuntimeError(f"All weather oracles failed for ({lat}, {lon}).") from exc


async def _fetch_nws_weather(lat: float, lon: float) -> Dict[str, Any]:
    if _http is None:
        raise RuntimeError("HTTP client not initialized.")
    points_url = f"{SETTINGS.NOAA_NWS_BASE}/points/{lat:.4f},{lon:.4f}"
    response = await _http.get(points_url, timeout=SETTINGS.HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    points = response.json()
    forecast_url = points["properties"]["forecast"]
    forecast_response = await _http.get(forecast_url, timeout=SETTINGS.HTTP_TIMEOUT_SECONDS)
    forecast_response.raise_for_status()
    period = forecast_response.json()["properties"]["periods"][0]
    return {"temperature_f": period.get("temperature"), "temperature_unit": period.get("temperatureUnit", "F"), "humidity": None, "wind_speed": period.get("windSpeed"), "short_forecast": period.get("shortForecast"), "source": "NOAA_NWS", "cached_at": datetime.now(timezone.utc).isoformat()}


async def _fetch_open_meteo_weather(lat: float, lon: float) -> Dict[str, Any]:
    if _http is None:
        raise RuntimeError("HTTP client not initialized.")
    url = f"{SETTINGS.OPEN_METEO_URL}?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&temperature_unit=fahrenheit&wind_speed_unit=mph"
    response = await _http.get(url, timeout=SETTINGS.HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    current = response.json().get("current", {})
    return {"temperature_f": current.get("temperature_2m"), "temperature_unit": "F", "humidity": current.get("relative_humidity_2m"), "wind_speed": f"{current.get('wind_speed_10m', 0)} mph", "short_forecast": _open_meteo_code_to_text(current.get("weather_code")), "source": "Open-Meteo", "cached_at": datetime.now(timezone.utc).isoformat()}


def _open_meteo_code_to_text(code: Optional[int]) -> str:
    mapping = {0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain", 71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers", 95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail"}
    return mapping.get(code, "Unknown")


def weather_confidence(claim_temp_f: Optional[float], claim_conditions: Optional[str], weather_data: Dict[str, Any]) -> float:
    return 0.5 if weather_data.get("temperature_f") is not None else 0.0


class FapCoreUnavailable(RuntimeError):
    """FAP-Core did not provide a usable verification result."""


class FapCoreClient:
    """Transport adapter for the existing FAP-Core verification service."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def verify(self, base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self.client.post(f"{base_url.rstrip('/')}/verify", json=payload)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("FAP-Core returned a non-object response.")
            return data
        except Exception as exc:
            raise FapCoreUnavailable(str(exc)) from exc

    async def health(self, base_url: str) -> bool:
        try:
            response = await self.client.get(f"{base_url.rstrip('/')}/health")
            response.raise_for_status()
            return True
        except Exception:
            return False
