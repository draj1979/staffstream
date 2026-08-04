import uuid
from datetime import UTC, datetime, timedelta

import httpx
from skill_marketplace import crud
from skill_marketplace.connectors import TokenSet
from skill_marketplace.crypto import decrypt_token

from auth import encode_access_token, encode_state_token
from tenancy import reset_current_tenant_id, set_current_tenant_id


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


async def _connect_slack(client, http_handler, tenant_id, employee_id):
    h = headers(tenant_id, employee_id)
    await client.put("/skills/slack/enablement", json={"enabled": True, "config": {}}, headers=h)
    http_handler.handler = _slack_oauth_handler
    state = encode_state_token(
        {"tenant_id": str(tenant_id), "employee_id": str(employee_id), "skill_id": "slack"}
    )
    resp = await client.get("/connections/slack/callback", params={"code": "c1", "state": state})
    assert resp.status_code == 200


async def test_invoke_requires_skill_enabled(client):
    resp = await client.post(
        "/skills/slack/invoke",
        json={"tool_name": "slack_post_message", "input": {}},
        headers=headers(uuid.uuid4(), uuid.uuid4()),
    )
    assert resp.status_code == 403


async def test_invoke_requires_employee_connection(client):
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    h = headers(tenant_id, employee_id)
    await client.put("/skills/slack/enablement", json={"enabled": True, "config": {}}, headers=h)

    resp = await client.post(
        "/skills/slack/invoke", json={"tool_name": "slack_post_message", "input": {}}, headers=h
    )
    assert resp.status_code == 403
    assert "connected" in resp.json()["detail"].lower()


async def test_invoke_unknown_skill_is_404(client):
    resp = await client.post(
        "/skills/not-a-skill/invoke",
        json={"tool_name": "x", "input": {}},
        headers=headers(uuid.uuid4(), uuid.uuid4()),
    )
    assert resp.status_code == 404


async def test_invoke_calls_provider_with_employees_own_token(client, http_handler):
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    await _connect_slack(client, http_handler, tenant_id, employee_id)

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"ok": True, "ts": "1.1"})

    http_handler.handler = handler
    resp = await client.post(
        "/skills/slack/invoke",
        json={"tool_name": "slack_post_message", "input": {"channel_id": "C1", "text": "hi"}},
        headers=headers(tenant_id, employee_id),
    )
    assert resp.status_code == 200
    assert resp.json()["output"]["ok"] is True
    assert seen["auth"] == "Bearer xoxp-tok"  # the employee's own token, not a shared one


async def test_invoke_surfaces_provider_error_as_502(client, http_handler):
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    await _connect_slack(client, http_handler, tenant_id, employee_id)

    http_handler.handler = lambda r: httpx.Response(
        200, json={"ok": False, "error": "not_in_channel"}
    )
    resp = await client.post(
        "/skills/slack/invoke",
        json={"tool_name": "slack_post_message", "input": {"channel_id": "C1", "text": "hi"}},
        headers=headers(tenant_id, employee_id),
    )
    assert resp.status_code == 502


async def test_invoke_refreshes_expired_google_token_before_calling(
    client, http_handler, session_factory
):
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    h = headers(tenant_id, employee_id)
    await client.put(
        "/skills/google_calendar/enablement", json={"enabled": True, "config": {}}, headers=h
    )

    ctx = set_current_tenant_id(tenant_id)
    try:
        async with session_factory() as session:
            await crud.upsert_connection(
                session,
                employee_id,
                "google_calendar",
                TokenSet(
                    access_token="ya29.expired",
                    refresh_token="1//refresh-tok",
                    expires_at=datetime.now(UTC) - timedelta(minutes=5),
                    scope="calendar.events",
                    external_account="employee@example.com",
                ),
            )
    finally:
        reset_current_tenant_id(ctx)

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "ya29.fresh", "expires_in": 3600})
        if request.url.path == "/v1/userinfo":
            return httpx.Response(200, json={"email": "employee@example.com"})
        return httpx.Response(200, json={"id": "evt1"})

    http_handler.handler = handler
    resp = await client.post(
        "/skills/google_calendar/invoke",
        json={
            "tool_name": "calendar_create_event",
            "input": {
                "summary": "Sync",
                "start": "2026-08-10T10:00:00Z",
                "end": "2026-08-10T10:30:00Z",
            },
        },
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["output"]["id"] == "evt1"
    assert "/token" in calls  # refresh actually happened before the real call

    ctx = set_current_tenant_id(tenant_id)
    try:
        async with session_factory() as session:
            connection = await crud.get_connection(session, employee_id, "google_calendar")
            assert decrypt_token(connection.access_token_encrypted) == "ya29.fresh"
    finally:
        reset_current_tenant_id(ctx)
