"""
FAP-Insurance — API Key Authentication
FastAPI dependency. Hardcoded key from env. Production rotation ready.
"""

from __future__ import annotations

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from config import SETTINGS
from logger import log

api_key_header = APIKeyHeader(
    name=SETTINGS.API_KEY_HEADER,
    auto_error=False,
)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Dependency: validate the X-API-Key header."""
    if not api_key:
        log.warning("auth.missing_key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required.",
        )
    if api_key != SETTINGS.API_KEY:
        log.warning("auth.invalid_key", key_prefix=api_key[:8])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
    return api_key
