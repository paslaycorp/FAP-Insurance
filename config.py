"""FAP-Insurance production configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass


_RENDER_DEFAULT_ENV = "production" if os.getenv("RENDER", "").lower() == "true" else "development"


@dataclass(frozen=True, slots=True)
class Settings:
    SERVICE_NAME: str = "fap-insurance"
    VERSION: str = "0.3.0-grand-slam"
    ENV: str = os.getenv("FAP_ENV", _RENDER_DEFAULT_ENV).strip().lower()
    HOST: str = os.getenv("FAP_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("FAP_PORT", "8000"))
    WORKERS: int = int(os.getenv("FAP_WORKERS", "1"))
    API_KEY_HEADER: str = "X-API-Key"
    API_KEY: str = os.getenv("FAP_API_KEY", "")
    RATE_LIMIT_PILOT: str = "100/minute"
    RATE_LIMIT_PROD: str = "1000/minute"
    RATE_LIMIT_BURST: str = "10/second"
    RATE_LIMIT_VERIFY: str = "100/minute"
    RATE_LIMIT_BATCH: str = "10/minute"
    RATE_LIMIT_DEMO: str = "10/second"
    FAP_CORE_URL: str = os.getenv("FAP_CORE_URL", "http://localhost:8000")
    FAP_CORE_API_KEY: str = os.getenv("FAP_CORE_API_KEY", "")
    FAP_CORE_TIMEOUT: float = 30.0
    NOAA_SWPC_URL: str = "https://services.swpc.noaa.gov/json/goes/primary/xrays-7-day.json"
    NOAA_NWS_BASE: str = "https://api.weather.gov"
    OPEN_METEO_URL: str = "https://api.open-meteo.com/v1/forecast"
    WEATHER_CACHE_TTL_SECONDS: int = 300
    SOLAR_CACHE_TTL_SECONDS: int = 60
    HTTP_TIMEOUT_SECONDS: float = 10.0
    WEIGHT_SOLAR: float = 0.30
    WEIGHT_SIGNATURE: float = 0.20
    WEIGHT_HARDWARE: float = 0.15
    WEIGHT_WEATHER: float = 0.15
    WEIGHT_WITNESS: float = 0.10
    WEIGHT_GPS: float = 0.10
    THRESHOLD_STRICT: float = 0.90
    THRESHOLD_PROBABLE: float = 0.70
    THRESHOLD_SUSPICIOUS: float = 0.40
    STRICT_LABEL: str = "Verified"
    PROBABLE_LABEL: str = "Likely Authentic"
    SUSPICIOUS_LABEL: str = "Suspicious"
    QUARANTINE_LABEL: str = "Fraudulent"
    LOG_LEVEL: str = os.getenv("FAP_LOG_LEVEL", "INFO")
    LOG_JSON: bool = os.getenv("FAP_LOG_JSON", "true").lower() == "true"

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    def validate_runtime(self) -> None:
        if not self.is_production:
            return

        missing = [
            name
            for name, value in (
                ("FAP_API_KEY", self.API_KEY),
                ("FAP_CORE_API_KEY", self.FAP_CORE_API_KEY),
            )
            if not value.strip()
        ]
        if missing:
            raise RuntimeError(
                "Missing required production configuration: " + ", ".join(missing)
            )

        core_url = self.FAP_CORE_URL.rstrip("/")
        if not core_url.startswith("https://") or core_url in {
            "http://localhost:8000",
            "https://localhost:8000",
        }:
            raise RuntimeError(
                "FAP_CORE_URL must identify a non-local HTTPS service in production"
            )


SETTINGS = Settings()
config = SETTINGS
