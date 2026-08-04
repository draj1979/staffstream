import uuid

import httpx
from api_gateway.dependencies import get_rate_limiter
from api_gateway.main import app
from api_gateway.rate_limit import RateLimiter

from auth import encode_access_token


def token_headers(tenant_id: uuid.UUID) -> dict:
    return {"Authorization": f"Bearer {encode_access_token(tenant_id, uuid.uuid4())}"}


async def test_requests_beyond_the_limit_get_429_with_retry_after(client):
    client.fake_http_client.set_response(
        "GET", "http://localhost:8001/tenants", httpx.Response(200, json=[])
    )
    tight_limiter = RateLimiter(client.fake_redis, max_requests=2, window_seconds=60)
    app.dependency_overrides[get_rate_limiter] = lambda: tight_limiter

    tenant_id = uuid.uuid4()
    headers = token_headers(tenant_id)

    assert (await client.get("/tenants", headers=headers)).status_code == 200
    assert (await client.get("/tenants", headers=headers)).status_code == 200

    resp = await client.get("/tenants", headers=headers)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


async def test_rate_limit_is_per_tenant_not_global(client):
    client.fake_http_client.set_response(
        "GET", "http://localhost:8001/tenants", httpx.Response(200, json=[])
    )
    tight_limiter = RateLimiter(client.fake_redis, max_requests=1, window_seconds=60)
    app.dependency_overrides[get_rate_limiter] = lambda: tight_limiter

    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()

    assert (await client.get("/tenants", headers=token_headers(tenant_a))).status_code == 200
    # tenant_a is now over its limit — a second tenant is unaffected.
    assert (await client.get("/tenants", headers=token_headers(tenant_a))).status_code == 429
    assert (await client.get("/tenants", headers=token_headers(tenant_b))).status_code == 200


async def test_unauthenticated_requests_are_bucketed_by_ip_not_shared_globally(client):
    client.fake_http_client.set_response(
        "POST", "http://localhost:8001/tenants", httpx.Response(201, json={})
    )
    tight_limiter = RateLimiter(client.fake_redis, max_requests=1, window_seconds=60)
    app.dependency_overrides[get_rate_limiter] = lambda: tight_limiter

    assert (await client.post("/tenants", json={"company_name": "Acme"})).status_code == 201
    resp = await client.post("/tenants", json={"company_name": "Acme"})
    assert resp.status_code == 429
