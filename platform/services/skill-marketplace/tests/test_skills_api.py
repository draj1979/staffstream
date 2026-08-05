import uuid

from auth import encode_access_token
from events import ROUTING_KEY_AUDIT, AuditEvent


def headers(tenant_id: uuid.UUID, employee_id: uuid.UUID | None = None) -> dict:
    token = encode_access_token(tenant_id, employee_id or uuid.uuid4())
    return {"Authorization": f"Bearer {token}"}


def admin_headers(tenant_id: uuid.UUID, employee_id: uuid.UUID | None = None) -> dict:
    token = encode_access_token(tenant_id, employee_id or uuid.uuid4(), role="admin")
    return {"Authorization": f"Bearer {token}"}


async def test_list_skills_requires_auth(client):
    resp = await client.get("/skills")
    assert resp.status_code == 401


async def test_catalog_skills_start_disabled(client):
    tenant_id = uuid.uuid4()
    resp = await client.get("/skills", headers=headers(tenant_id))
    assert resp.status_code == 200
    body = {s["skill_id"]: s for s in resp.json()}
    assert set(body) == {"slack", "google_calendar"}
    assert body["slack"]["enabled"] is False
    assert body["google_calendar"]["enabled"] is False


async def test_enablement_requires_admin_role(client):
    tenant_id = uuid.uuid4()
    resp = await client.put(
        "/skills/slack/enablement", json={"enabled": True, "config": {}}, headers=headers(tenant_id)
    )
    assert resp.status_code == 403


async def test_enabling_a_skill_is_tenant_scoped(client):
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()

    resp = await client.put(
        "/skills/slack/enablement",
        json={"enabled": True, "config": {}},
        headers=admin_headers(tenant_a),
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True

    resp_a = await client.get("/skills", headers=headers(tenant_a))
    resp_b = await client.get("/skills", headers=headers(tenant_b))
    slack_a = next(s for s in resp_a.json() if s["skill_id"] == "slack")
    slack_b = next(s for s in resp_b.json() if s["skill_id"] == "slack")
    assert slack_a["enabled"] is True
    assert slack_b["enabled"] is False  # opt-in per tenant, not global


async def test_enablement_is_idempotent_upsert(client):
    tenant_id = uuid.uuid4()
    h = admin_headers(tenant_id)

    await client.put(
        "/skills/slack/enablement", json={"enabled": True, "config": {"x": 1}}, headers=h
    )
    resp = await client.put(
        "/skills/slack/enablement", json={"enabled": False, "config": {"x": 2}}, headers=h
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["config"] == {"x": 2}

    resp = await client.get("/skills", headers=h)
    assert len([s for s in resp.json() if s["skill_id"] == "slack"]) == 1  # no duplicate row


async def test_enablement_for_unknown_skill_is_404(client):
    resp = await client.put(
        "/skills/not-a-real-skill/enablement",
        json={"enabled": True, "config": {}},
        headers=admin_headers(uuid.uuid4()),
    )
    assert resp.status_code == 404


async def test_enablement_publishes_audit_event(client, fake_publisher):
    tenant_id = uuid.uuid4()
    resp = await client.put(
        "/skills/slack/enablement",
        json={"enabled": True, "config": {}},
        headers=admin_headers(tenant_id),
    )
    assert resp.status_code == 200

    await fake_publisher.wait_for_publish()
    routing_key, payload = fake_publisher.published[0]
    assert routing_key == ROUTING_KEY_AUDIT
    event = AuditEvent.model_validate_json(payload)
    assert event.action == "skill.enablement_changed"
    assert event.target_id == "slack"
    assert event.metadata == {"enabled": True}


async def test_tools_empty_when_skill_not_enabled(client):
    resp = await client.get("/tools", headers=headers(uuid.uuid4()))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_tools_empty_when_enabled_but_employee_not_connected(client):
    tenant_id = uuid.uuid4()
    h = headers(tenant_id)
    await client.put(
        "/skills/slack/enablement",
        json={"enabled": True, "config": {}},
        headers=admin_headers(tenant_id),
    )

    resp = await client.get("/tools", headers=h)
    assert resp.status_code == 200
    assert resp.json() == []  # enabled for the tenant, but this employee hasn't connected yet
