"""
FAP-Insurance — Production Settings
Hardcoded defaults. Env overrides. No secrets in source.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    SERVICE_NAME: str = "fap-insurance"
    VERSION: str = "0.3.0-grand-slam"
    ENV: str = os.getenv("FAP_ENV", "production")
    HOST: str = os.getenv("FAP_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("FAP_PORT", "8001"))
    API_KEY_HEADER: str = "X-API-Key"
    API_KEY: str = os.getenv(
        "FAP_API_KEY",
        "dev-fap-key-7a3f9e2d-8842-4b91-b3c7-1e8d6f5a2c09",
    )
    RATE_LIMIT_VERIFY: str = os.getenv("FAP_RATE_LIMIT", "100/minute")
    RATE_LIMIT_BATCH: str = "10/minute"
    RATE_LIMIT_DEMO: str = "10/second"
    FAP_CORE_URL: str = os.getenv("FAP_CORE_URL", "http://localhost:8000")
    FAP_CORE_TIMEOUT: float = 30.0
    FAP_CORE_CACHE_TTL: int = 300
    NOAA_SWPC_URL: str = "https://services.swpc.noaa.gov/json/goes/primary/xrays-7-day.json"
    NOAA_NWS_BASE: str = "https://api.weather.gov"
    OPEN_METEO_URL: str = "https://api.open-meteo.com/v1/forecast"
    HTTP_TIMEOUT_SECONDS: float = 10.0
    LOG_LEVEL: str = os.getenv("FAP_LOG_LEVEL", "INFO")
    LOG_JSON: bool = os.getenv("FAP_LOG_JSON", "true").lower() == "true"
    AUDIT_DB_PATH: str = os.getenv("FAP_AUDIT_DB", "fap_audit.db")
    AUDIT_LOCK_TIMEOUT_SECONDS: float = 5.0

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"


SETTINGS = Settings()
