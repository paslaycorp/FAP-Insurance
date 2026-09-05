"""
FAP-Insurance — API Key Authentication
FastAPI dependency. Hardcoded key from env. Production rotation ready.
"""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from config import SETTINGS
from logger import log

api_key_header = APIKeyHeader(
    name=SETTINGS.API_KEY_HEADER,
    auto_error=False,
)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Dependency: validate the X-API-Key header without leaking key material."""
    if not api_key:
        log.warning("auth.missing_key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required.",
        )
    if not SETTINGS.API_KEY or not hmac.compare_digest(api_key, SETTINGS.API_KEY):
        log.warning("auth.invalid_key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
    return api_key
