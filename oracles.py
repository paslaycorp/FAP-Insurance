"""FAP-Insurance external oracle adapters."""
from __future__ import annotations
import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import httpx
from cachetools import TTLCache
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from config import SETTINGS
from epm_exchange import AssuranceAttestation, AssuranceRequest, ReplayGuard, digest_hex, verify_attestation
from logger import log
_solar_cache: TTLCache = TTLCache(maxsize=128, ttl=SETTINGS.SOLAR_CACHE_TTL_SECONDS)
_weather_cache: TTLCache = TTLCache(maxsize=256, ttl=SETTINGS.WEATHER_CACHE_TTL_SECONDS)
_http: Optional[httpx.AsyncClient] = None
def set_http_client(client: httpx.AsyncClient) -> None:
    global _http; _http = client
async def fetch_solar_flux() -> Dict[str, Any]:
    cache_key = "solar:latest"
    if cache_key in _solar_cache: return _solar_cache[cache_key]
    if _http is None: raise RuntimeError("HTTP client not initialized.")
    try:
        response = await _http.get(SETTINGS.NOAA_SWPC_URL, timeout=SETTINGS.HTTP_TIMEOUT_SECONDS); response.raise_for_status(); data = response.json()
        if not isinstance(data, list) or not data: raise ValueError("Empty or malformed SWPC response.")
        latest = data[-1]; result = {"flux": latest.get("flux", 0.0), "energy": latest.get("energy", ""), "time_tag": latest.get("time_tag", ""), "source": "NOAA_SWPC", "cached_at": datetime.now(timezone.utc).isoformat()}; _solar_cache[cache_key] = result; return result
    except Exception as exc: log.error("solar.fetch_failed", error=str(exc)); raise
def solar_confidence(claim_time: datetime, solar_data: Dict[str, Any]) -> float:
    import math
    flux = solar_data.get("flux", 0.0)
    if flux == 0.0: return 0.0
    return round(min(1.0, max(0.0, math.log10(flux + 1e-10) + 9) / 6), 4)
def _weather_cache_key(lat: float, lon: float) -> str: return f"weather:{round(lat, 2)}:{round(lon, 2)}"
async def fetch_weather(lat: float, lon: float) -> Dict[str, Any]:
    cache_key = _weather_cache_key(lat, lon)
    if cache_key in _weather_cache: return _weather_cache[cache_key]
    if _http is None: raise RuntimeError("HTTP client not initialized.")
    try:
        result = await _fetch_nws_weather(lat, lon); _weather_cache[cache_key] = result; return result
    except Exception as exc: log.warning("weather.nws_failed", error=str(exc), lat=lat, lon=lon)
    try:
        result = await _fetch_open_meteo_weather(lat, lon); _weather_cache[cache_key] = result; return result
    except Exception as exc: log.error("weather.openmeteo_failed", error=str(exc), lat=lat, lon=lon); raise RuntimeError(f"All weather oracles failed for ({lat}, {lon}).") from exc
async def _fetch_nws_weather(lat: float, lon: float) -> Dict[str, Any]:
    if _http is None: raise RuntimeError("HTTP client not initialized.")
    response = await _http.get(f"{SETTINGS.NOAA_NWS_BASE}/points/{lat:.4f},{lon:.4f}", timeout=SETTINGS.HTTP_TIMEOUT_SECONDS); response.raise_for_status(); forecast_url = response.json()["properties"]["forecast"]
    forecast_response = await _http.get(forecast_url, timeout=SETTINGS.HTTP_TIMEOUT_SECONDS); forecast_response.raise_for_status(); period = forecast_response.json()["properties"]["periods"][0]
    return {"temperature_f": period.get("temperature"), "temperature_unit": period.get("temperatureUnit", "F"), "humidity": None, "wind_speed": period.get("windSpeed"), "short_forecast": period.get("shortForecast"), "source": "NOAA_NWS", "cached_at": datetime.now(timezone.utc).isoformat()}
async def _fetch_open_meteo_weather(lat: float, lon: float) -> Dict[str, Any]:
    if _http is None: raise RuntimeError("HTTP client not initialized.")
    response = await _http.get(f"{SETTINGS.OPEN_METEO_URL}?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&temperature_unit=fahrenheit&wind_speed_unit=mph", timeout=SETTINGS.HTTP_TIMEOUT_SECONDS); response.raise_for_status(); current = response.json().get("current", {})
    return {"temperature_f": current.get("temperature_2m"), "temperature_unit": "F", "humidity": current.get("relative_humidity_2m"), "wind_speed": f"{current.get('wind_speed_10m', 0)} mph", "short_forecast": _open_meteo_code_to_text(current.get("weather_code")), "source": "Open-Meteo", "cached_at": datetime.now(timezone.utc).isoformat()}
def _open_meteo_code_to_text(code: Optional[int]) -> str: return {0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain", 71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers", 95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail"}.get(code, "Unknown")
def weather_confidence(claim_temp_f: Optional[float], claim_conditions: Optional[str], weather_data: Dict[str, Any]) -> float: return 0.5 if weather_data.get("temperature_f") is not None else 0.0
class FapCoreUnavailable(RuntimeError): pass
class FapCoreClient:
    """Transport adapter for FAP-Core with Phase-1 bearer auth and EPM attestation verification."""
    def __init__(self, client: httpx.AsyncClient): self.client = client
    async def verify(self, base_url: str, payload: Dict[str, Any], assurance_header: Optional[str] = None) -> Dict[str, Any]:
        try:
            if not SETTINGS.FAP_CORE_API_KEY: raise RuntimeError("FAP-Core service credential is not configured")
            headers = {"Authorization": f"Bearer {SETTINGS.FAP_CORE_API_KEY}"}
            if assurance_header: headers["X-EPM-Assurance"] = assurance_header
            response = await self.client.post(f"{base_url.rstrip('/')}/verify", json=payload, headers=headers); response.raise_for_status(); data = response.json()
            if not isinstance(data, dict): raise ValueError("FAP-Core returned a non-object response.")
            return data
        except Exception as exc: raise FapCoreUnavailable(str(exc)) from exc
    async def verify_assured(self, base_url: str, payload: Dict[str, Any], *, claim_id: str, evidence_id: str, timestamp_claimed: datetime, purpose: str, scope: str, jurisdiction: str, rule_id: str, rule_version: str, authority: str, consequence: str) -> Dict[str, Any]:
        request = AssuranceRequest.create(claim_id=claim_id, evidence_id=evidence_id, media_hash=payload["media_hash"], timestamp_claimed=timestamp_claimed, purpose=purpose, scope=scope, jurisdiction=jurisdiction, rule_id=rule_id, rule_version=rule_version, authority=authority, consequence=consequence, requester_service_id=SETTINGS.EPM_SERVICE_ID, verification_input_digest=digest_hex(payload))
        encoded = base64.urlsafe_b64encode(json.dumps(request.payload(), default=lambda x: x.isoformat() if isinstance(x, datetime) else x, ensure_ascii=False, separators=(",", ":")).encode()).rstrip(b"=").decode()
        wire_payload = json.loads(json.dumps(payload, default=lambda x: x.isoformat() if isinstance(x, datetime) else x))
        data = await self.verify(base_url, wire_payload, assurance_header=encoded)
        raw = data.get("epm_attestation")
        if not isinstance(raw, dict): raise FapCoreUnavailable("FAP-Core did not return an EPM attestation")
        try:
            processed = datetime.fromisoformat(raw["processed_at"].replace("Z", "+00:00"))
            attestation = AssuranceAttestation(raw["request_id"], raw["nonce"], raw["request_digest"], raw["response_digest"], raw["evidence_id"], raw["artifact_id"], raw["engine_id"], raw["engine_version"], raw["policy_id"], raw["policy_version"], tuple(raw.get("oracle_versions", [])), processed, raw["result"], raw.get("confidence"), raw.get("failure_state"), raw["responder_service_id"], raw["signature"])
            if not SETTINGS.FAP_CORE_PUBLIC_KEY: raise ValueError("FAP-Core public attestation key is not configured")
            key = Ed25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(SETTINGS.FAP_CORE_PUBLIC_KEY + "=" * (-len(SETTINGS.FAP_CORE_PUBLIC_KEY) % 4)))
            verify_attestation(request, attestation, trusted_keys={SETTINGS.FAP_CORE_SERVICE_ID: key}, replay_guard=_FAP_REPLAY_GUARD, expected_engine_id=SETTINGS.FAP_CORE_SERVICE_ID, expected_evidence_id=evidence_id)
        except Exception as exc: raise FapCoreUnavailable("FAP-Core attestation verification failed") from exc
        return data
    async def health(self, base_url: str) -> bool:
        try:
            response = await self.client.get(f"{base_url.rstrip('/')}/health"); response.raise_for_status(); return True
        except Exception: return False
_FAP_REPLAY_GUARD = ReplayGuard()
