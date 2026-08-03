"""
FAP-Insurance — Production Configuration
Hardcoded. Explicit. No env-var footguns for core constants.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable production settings."""

    # ── Service identity ─────────────────────────────────────
    SERVICE_NAME: str = "fap-insurance"
    VERSION: str = "0.3.0-grand-slam"
    ENV: str = os.getenv("FAP_ENV", "production")

    # ── Network ──────────────────────────────────────────────
    HOST: str = os.getenv("FAP_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("FAP_PORT", "8000"))
    WORKERS: int = int(os.getenv("FAP_WORKERS", "1"))

    # ── Authentication ───────────────────────────────────────
    API_KEY_HEADER: str = "X-API-Key"
    # Rotate by env; default is a DEV key never used in prod.
    API_KEY: str = os.getenv(
        "FAP_API_KEY",
        "dev-fap-key-7a3f9e2d-8842-4b91-b3c7-1e8d6f5a2c09",
    )

    # ── Rate limiting ────────────────────────────────────────
    RATE_LIMIT_PILOT: str = "100/minute"
    RATE_LIMIT_PROD: str = "1000/minute"
    RATE_LIMIT_BURST: str = "10/second"

    # ── NOAA / Weather ───────────────────────────────────────
    NOAA_SWPC_URL: str = "https://services.swpc.noaa.gov/json/goes/primary/xrays-7-day.json"
    NOAA_NWS_BASE: str = "https://api.weather.gov"
    OPEN_METEO_URL: str = "https://api.open-meteo.com/v1/forecast"
    WEATHER_CACHE_TTL_SECONDS: int = 300          # 5 min
    SOLAR_CACHE_TTL_SECONDS: int = 60             # 1 min
    HTTP_TIMEOUT_SECONDS: float = 10.0

    # ── Scoring weights (must sum to 1.0) ────────────────────
    WEIGHT_SOLAR: float = 0.30
    WEIGHT_SIGNATURE: float = 0.20
    WEIGHT_HARDWARE: float = 0.15
    WEIGHT_WEATHER: float = 0.15
    WEIGHT_WITNESS: float = 0.10
    WEIGHT_GPS: float = 0.10

    # ── Verdict thresholds ───────────────────────────────────
    THRESHOLD_STRICT: float = 0.90
    THRESHOLD_PROBABLE: float = 0.70
    THRESHOLD_SUSPICIOUS: float = 0.40

    # ── Logging ──────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("FAP_LOG_LEVEL", "INFO")
    LOG_JSON: bool = os.getenv("FAP_LOG_JSON", "true").lower() == "true"

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"


# Singleton — import once, use everywhere.
SETTINGS = Settings()
