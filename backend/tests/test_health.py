import re

import pytest


@pytest.mark.anyio
async def test_health_returns_200(client):
    response = await client.get("/api/health")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_health_status_ok(client):
    response = await client.get("/api/health")
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.anyio
async def test_health_version_format(client):
    response = await client.get("/api/health")
    data = response.json()
    assert re.match(r"^\d+\.\d+\.\d+$", data["version"])


@pytest.mark.anyio
async def test_health_response_schema(client):
    response = await client.get("/api/health")
    data = response.json()
    assert set(data.keys()) == {"status", "version"}


@pytest.mark.anyio
async def test_cors_allows_nuxt_origin(client):
    response = await client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


@pytest.mark.anyio
async def test_cors_blocks_unknown_origin(client):
    response = await client.options(
        "/api/health",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    allow = response.headers.get("access-control-allow-origin", "")
    assert allow != "http://evil.com"
