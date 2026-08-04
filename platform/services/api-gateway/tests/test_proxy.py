import uuid

import httpx

from auth import encode_access_token


def user_headers() -> dict:
    token = encode_access_token(uuid.uuid4(), uuid.uuid4())
    return {"Authorization": f"Bearer {token}"}


async def test_unmapped_path_is_404(client):
    resp = await client.get("/nonexistent-thing")
    assert resp.status_code == 404


async def test_routes_to_correct_upstream_by_path(client):
    client.fake_http_client.set_response(
        "GET", "http://localhost:8002/employees", httpx.Response(200, json=[{"email": "a@b.com"}])
    )

    resp = await client.get("/employees", headers=user_headers())
    assert resp.status_code == 200
    assert resp.json() == [{"email": "a@b.com"}]

    method, url, _ = client.fake_http_client.calls[-1]
    assert method == "GET"
    assert url == "http://localhost:8002/employees"


async def test_forwards_subpaths_and_query_params(client):
    employee_id = str(uuid.uuid4())
    client.fake_http_client.set_response(
        "GET",
        f"http://localhost:8002/employees/{employee_id}",
        httpx.Response(200, json={"employee_id": employee_id}),
    )

    resp = await client.get(f"/employees/{employee_id}?limit=5", headers=user_headers())
    assert resp.status_code == 200

    method, url, kwargs = client.fake_http_client.calls[-1]
    assert url == f"http://localhost:8002/employees/{employee_id}"
    assert ("limit", "5") in kwargs["params"]


async def test_4xx_from_upstream_passes_through_unchanged(client):
    client.fake_http_client.set_response(
        "GET", "http://localhost:8004/agents/x", httpx.Response(404, json={"detail": "not found"})
    )

    resp = await client.get("/agents/x", headers=user_headers())
    assert resp.status_code == 404
    assert resp.json() == {"detail": "not found"}


async def test_5xx_body_from_upstream_is_sanitized(client):
    leaky_body = {
        "detail": "sqlalchemy.exc.IntegrityError: duplicate key value violates "
        "unique constraint on table agents at 10.0.4.7:5432"
    }
    client.fake_http_client.set_response(
        "GET", "http://localhost:8004/agents", httpx.Response(500, json=leaky_body)
    )

    resp = await client.get("/agents", headers=user_headers())
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    assert "sqlalchemy" not in resp.text
    assert "10.0.4.7" not in resp.text


async def test_upstream_connection_failure_returns_sanitized_502(client):
    client.fake_http_client.set_error(
        "GET", "http://localhost:8001/tenants", httpx.ConnectError("connection refused")
    )

    resp = await client.get("/tenants")
    assert resp.status_code == 502
    assert resp.json() == {"detail": "Upstream service unavailable"}


async def test_oversized_body_is_rejected(client):
    from api_gateway.config import settings

    big = b"x" * (settings.max_body_bytes + 1)
    resp = await client.post("/employees", content=big, headers=user_headers())
    assert resp.status_code == 413


async def test_upload_path_gets_the_higher_size_ceiling(client):
    from api_gateway.config import settings

    just_over_default = b"x" * (settings.max_body_bytes + 1)
    assert len(just_over_default) < settings.max_upload_body_bytes

    client.fake_http_client.set_response(
        "POST", "http://localhost:8008/documents", httpx.Response(201, json={"status": "ready"})
    )
    resp = await client.post(
        "/documents", content=just_over_default, headers=user_headers()
    )
    assert resp.status_code == 201


async def test_hop_by_hop_request_headers_are_not_forwarded(client):
    client.fake_http_client.set_response(
        "GET", "http://localhost:8002/employees", httpx.Response(200, json=[])
    )

    await client.get(
        "/employees",
        headers={**user_headers(), "Connection": "keep-alive"},
    )

    _, _, kwargs = client.fake_http_client.calls[-1]
    forwarded_header_names = {k.lower() for k in kwargs["headers"]}
    assert "connection" not in forwarded_header_names
    assert "host" not in forwarded_header_names
