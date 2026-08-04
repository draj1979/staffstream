import uuid
from urllib.parse import parse_qs, urlparse

import httpx

from auth import encode_access_token, encode_state_token


def headers(tenant_id: uuid.UUID, employee_id: uuid.UUID) -> dict:
    token = encode_access_token(tenant_id, employee_id)
    return {"Authorization": f"Bearer {token}"}


def _slack_oauth_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "ok": True,
            "authed_user": {"id": "U1", "access_token": "xoxp-tok", "scope": "chat:write"},
        },
    )


async def test_authorize_requires_skill_enabled_first(client):
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    resp = await client.get(
        "/connections/slack/authorize", headers=headers(tenant_id, employee_id)
    )
    assert resp.status_code == 403


async def test_authorize_redirects_to_provider_with_signed_state(client):
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    h = headers(tenant_id, employee_id)
    await client.put("/skills/slack/enablement", json={"enabled": True, "config": {}}, headers=h)

    resp = await client.get("/connections/slack/authorize", headers=h, follow_redirects=False)
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert location.startswith("https://slack.com/oauth/v2/authorize")
    query = parse_qs(urlparse(location).query)
    assert "state" in query
    assert "user_scope" in query


async def test_authorize_unknown_skill_is_404(client):
    resp = await client.get(
        "/connections/not-a-skill/authorize", headers=headers(uuid.uuid4(), uuid.uuid4())
    )
    assert resp.status_code == 404


async def test_callback_exchanges_code_and_stores_connection(client, http_handler):
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    h = headers(tenant_id, employee_id)
    await client.put("/skills/slack/enablement", json={"enabled": True, "config": {}}, headers=h)

    http_handler.handler = _slack_oauth_handler
    state = encode_state_token(
        {"tenant_id": str(tenant_id), "employee_id": str(employee_id), "skill_id": "slack"}
    )
    resp = await client.get(
        "/connections/slack/callback", params={"code": "authcode123", "state": state}
    )
    assert resp.status_code == 200
    assert "Connected" in resp.text

    resp = await client.get("/connections", headers=h)
    connections = {c["skill_id"]: c for c in resp.json()}
    assert connections["slack"]["connected"] is True
    assert connections["slack"]["external_account"] == "U1"
    assert connections["google_calendar"]["connected"] is False


async def test_callback_rejects_forged_state(client):
    resp = await client.get(
        "/connections/slack/callback",
        params={"code": "authcode123", "state": "not-a-real-signed-token"},
    )
    assert resp.status_code == 400


async def test_callback_rejects_state_for_a_different_skill(client, http_handler):
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    # state was minted for google_calendar, but the callback URL says slack
    state = encode_state_token(
        {
            "tenant_id": str(tenant_id),
            "employee_id": str(employee_id),
            "skill_id": "google_calendar",
        }
    )
    resp = await client.get(
        "/connections/slack/callback", params={"code": "authcode123", "state": state}
    )
    assert resp.status_code == 400


async def test_callback_surfaces_provider_error(client):
    resp = await client.get(
        "/connections/slack/callback", params={"error": "access_denied"}
    )
    assert resp.status_code == 400


async def test_connection_is_scoped_to_the_connecting_employee(client, http_handler):
    tenant_id = uuid.uuid4()
    employee_a, employee_b = uuid.uuid4(), uuid.uuid4()
    h_a = headers(tenant_id, employee_a)
    h_b = headers(tenant_id, employee_b)
    await client.put("/skills/slack/enablement", json={"enabled": True, "config": {}}, headers=h_a)

    http_handler.handler = _slack_oauth_handler
    state = encode_state_token(
        {"tenant_id": str(tenant_id), "employee_id": str(employee_a), "skill_id": "slack"}
    )
    await client.get("/connections/slack/callback", params={"code": "c1", "state": state})

    resp_a = await client.get("/connections", headers=h_a)
    resp_b = await client.get("/connections", headers=h_b)
    assert next(c for c in resp_a.json() if c["skill_id"] == "slack")["connected"] is True
    assert next(c for c in resp_b.json() if c["skill_id"] == "slack")["connected"] is False


async def test_disconnect_removes_the_connection(client, http_handler):
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    h = headers(tenant_id, employee_id)
    await client.put("/skills/slack/enablement", json={"enabled": True, "config": {}}, headers=h)
    http_handler.handler = _slack_oauth_handler
    state = encode_state_token(
        {"tenant_id": str(tenant_id), "employee_id": str(employee_id), "skill_id": "slack"}
    )
    await client.get("/connections/slack/callback", params={"code": "c1", "state": state})

    resp = await client.delete("/connections/slack", headers=h)
    assert resp.status_code == 204

    resp = await client.get("/connections", headers=h)
    assert next(c for c in resp.json() if c["skill_id"] == "slack")["connected"] is False


async def test_disconnect_when_not_connected_is_404(client):
    resp = await client.delete("/connections/slack", headers=headers(uuid.uuid4(), uuid.uuid4()))
    assert resp.status_code == 404
