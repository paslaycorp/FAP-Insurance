"""Render ASGI entrypoint with a platform readiness surface."""

from fastapi import Request, Response

from api import app
from settings import SETTINGS


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def render_readiness(request: Request):
    """Return a minimal readiness response for Render and operators."""
    if request.method == "HEAD":
        return Response(status_code=200, headers={"X-FAP-Service": "fap-insurance"})
    return {
        "service": "fap-insurance",
        "status": "ready",
        "version": SETTINGS.VERSION,
        "health": "/health",
    }
