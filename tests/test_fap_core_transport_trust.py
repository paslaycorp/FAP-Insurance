from __future__ import annotations

import pytest

from oracles import FapCoreClient, FapCoreUnavailable


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self):
        self.posts = []
        self.gets = []

    async def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return FakeResponse({"artifact_id": "evidence-1"})

    async def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return FakeResponse(
            {
                "status": "healthy",
                "service": "fap-core",
                "git_commit": "a" * 40,
                "git_repo_slug": "paslaycorp/FAP-Core-v0.2.0",
            }
        )


@pytest.mark.asyncio
async def test_fap_core_verify_uses_explicit_bearer_credential():
    http = FakeClient()
    client = FapCoreClient(http, api_key="service-secret")

    await client.verify("https://fap-core.example", {"artifact_id": "evidence-1"})

    assert http.posts[0][1]["headers"] == {"Authorization": "Bearer service-secret"}


@pytest.mark.asyncio
async def test_fap_core_verify_fails_closed_without_service_credential():
    client = FapCoreClient(FakeClient(), api_key="")

    with pytest.raises(FapCoreUnavailable, match="API key is not configured"):
        await client.verify("https://fap-core.example", {})


@pytest.mark.asyncio
async def test_runtime_identity_is_observed_from_health_and_cached():
    http = FakeClient()
    client = FapCoreClient(http, api_key="service-secret")

    first = await client.runtime_identity("https://fap-core.example")
    second = await client.runtime_identity("https://fap-core.example")

    assert first["git_commit"] == "a" * 40
    assert second == first
    assert len(http.gets) == 1
    assert http.gets[0][0] == "https://fap-core.example/auth/check"
    assert http.gets[0][1]["headers"] == {"Authorization": "Bearer service-secret"}


@pytest.mark.asyncio
async def test_runtime_identity_fails_closed_without_service_credential():
    client = FapCoreClient(FakeClient(), api_key="")

    with pytest.raises(FapCoreUnavailable, match="API key is not configured"):
        await client.runtime_identity("https://fap-core.example")
