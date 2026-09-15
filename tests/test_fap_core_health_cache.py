import asyncio

import httpx
import pytest

from oracles import FapCoreClient


@pytest.mark.asyncio
async def test_health_coalesces_concurrent_success_probes():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "healthy"}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = FapCoreClient(
            http,
            health_success_ttl_seconds=60.0,
            health_failure_ttl_seconds=60.0,
        )
        results = await asyncio.gather(
            client.health("https://fap-core.example"),
            client.health("https://fap-core.example"),
            client.health("https://fap-core.example"),
        )
        assert results == [True, True, True]
        assert calls == 1
        assert await client.health("https://fap-core.example") is True
        assert calls == 1


@pytest.mark.asyncio
async def test_health_failure_is_cached_without_inflation():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={"detail": "rate limited"}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = FapCoreClient(
            http,
            health_success_ttl_seconds=60.0,
            health_failure_ttl_seconds=60.0,
        )
        assert await client.health("https://fap-core.example") is False
        assert await client.health("https://fap-core.example") is False
        assert calls == 1


@pytest.mark.asyncio
async def test_health_reprobes_after_failure_cache_expires():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"detail": "rate limited"}, request=request)
        return httpx.Response(200, json={"status": "healthy"}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = FapCoreClient(
            http,
            health_success_ttl_seconds=60.0,
            health_failure_ttl_seconds=0.0,
        )
        assert await client.health("https://fap-core.example") is False
        assert await client.health("https://fap-core.example") is True
        assert calls == 2
