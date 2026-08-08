import uuid

from auth import encode_access_token, encode_system_token
from events import ROUTING_KEY_AUDIT, AuditEvent

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()


def system_headers(tenant_id: uuid.UUID) -> dict:
    return {"Authorization": f"Bearer {encode_system_token(tenant_id)}"}


def user_headers(
    tenant_id: uuid.UUID, employee_id: uuid.UUID | None = None, role: str = "employee"
) -> dict:
    token = encode_access_token(tenant_id, employee_id or uuid.uuid4(), role=role)
    return {"Authorization": f"Bearer {token}"}


def admin_headers(tenant_id: uuid.UUID) -> dict:
    return user_headers(tenant_id, role="admin")


def manager_headers(tenant_id: uuid.UUID) -> dict:
    return user_headers(tenant_id, role="manager")


async def test_missing_authorization_header_is_401(client):
    resp = await client.get("/agents")
    assert resp.status_code == 401


async def test_create_agent_with_system_token_applies_defaults(client):
    employee_id = uuid.uuid4()
    resp = await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tenant_id"] == str(TENANT_A)
    assert body["employee_id"] == str(employee_id)
    assert body["name"] == "Personal Assistant"
    assert body["provider"] == "claude"
    assert body["model"] == "claude-sonnet-5"
    assert body["temperature"] == 1.0
    assert body["memory_namespace"] == f"{TENANT_A}:{employee_id}"
    assert body["knowledge_sources"] == []


async def test_create_agent_with_explicit_provider(client):
    employee_id = uuid.uuid4()
    resp = await client.post(
        "/agents",
        json={"employee_id": str(employee_id), "provider": "openai", "model": "gpt-4o"},
        headers=system_headers(TENANT_A),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4o"


async def test_create_agent_with_user_token_also_works(client):
    resp = await client.post(
        "/agents", json={"employee_id": str(uuid.uuid4())}, headers=user_headers(TENANT_A)
    )
    assert resp.status_code == 201


async def test_second_agent_for_same_employee_is_conflict(client):
    employee_id = uuid.uuid4()
    resp = await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    assert resp.status_code == 201

    resp = await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    assert resp.status_code == 409


async def test_grant_skill_with_system_token_adds_to_allowlist(client):
    # This is the exact call Skill Marketplace makes the moment an
    # employee's OAuth connection for a skill succeeds — the employee
    # never logged in for this, so it has to work with a system token,
    # same as agent auto-creation.
    employee_id = uuid.uuid4()
    create_resp = await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    assert create_resp.json()["skills"] == []

    resp = await client.post(
        f"/agents/by-employee/{employee_id}/skills/github", headers=system_headers(TENANT_A)
    )
    assert resp.status_code == 200
    assert resp.json()["skills"] == ["github"]


async def test_grant_skill_is_idempotent(client):
    employee_id = uuid.uuid4()
    await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    await client.post(
        f"/agents/by-employee/{employee_id}/skills/github", headers=system_headers(TENANT_A)
    )
    resp = await client.post(
        f"/agents/by-employee/{employee_id}/skills/github", headers=system_headers(TENANT_A)
    )
    assert resp.status_code == 200
    assert resp.json()["skills"] == ["github"]


async def test_grant_skill_preserves_other_skills(client):
    employee_id = uuid.uuid4()
    await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    await client.post(
        f"/agents/by-employee/{employee_id}/skills/slack", headers=system_headers(TENANT_A)
    )
    resp = await client.post(
        f"/agents/by-employee/{employee_id}/skills/github", headers=system_headers(TENANT_A)
    )
    assert set(resp.json()["skills"]) == {"slack", "github"}


async def test_grant_skill_with_own_user_token_also_works(client):
    employee_id = uuid.uuid4()
    await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    resp = await client.post(
        f"/agents/by-employee/{employee_id}/skills/github",
        headers=user_headers(TENANT_A, employee_id),
    )
    assert resp.status_code == 200
    assert resp.json()["skills"] == ["github"]


async def test_grant_skill_for_unknown_employee_is_404(client):
    resp = await client.post(
        f"/agents/by-employee/{uuid.uuid4()}/skills/github", headers=system_headers(TENANT_A)
    )
    assert resp.status_code == 404


async def test_revoke_skill_removes_from_allowlist(client):
    employee_id = uuid.uuid4()
    await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    await client.post(
        f"/agents/by-employee/{employee_id}/skills/github", headers=system_headers(TENANT_A)
    )

    resp = await client.delete(
        f"/agents/by-employee/{employee_id}/skills/github", headers=system_headers(TENANT_A)
    )
    assert resp.status_code == 200
    assert resp.json()["skills"] == []


async def test_revoke_skill_not_present_is_a_no_op(client):
    employee_id = uuid.uuid4()
    await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    resp = await client.delete(
        f"/agents/by-employee/{employee_id}/skills/github", headers=system_headers(TENANT_A)
    )
    assert resp.status_code == 200
    assert resp.json()["skills"] == []


async def test_same_employee_id_allowed_in_different_tenants(client):
    employee_id = uuid.uuid4()
    resp = await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    assert resp.status_code == 201
    resp = await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_B)
    )
    assert resp.status_code == 201


async def test_agent_isolated_from_other_tenants(client):
    resp = await client.post(
        "/agents", json={"employee_id": str(uuid.uuid4())}, headers=system_headers(TENANT_A)
    )
    agent_id = resp.json()["agent_id"]

    resp = await client.get(f"/agents/{agent_id}", headers=admin_headers(TENANT_B))
    assert resp.status_code == 404

    resp = await client.get("/agents", headers=manager_headers(TENANT_B))
    assert resp.json() == []

    resp = await client.get("/agents", headers=manager_headers(TENANT_A))
    assert any(a["agent_id"] == agent_id for a in resp.json())


async def test_list_agents_requires_manager_or_above(client):
    resp = await client.get("/agents", headers=user_headers(TENANT_A))  # default "employee"
    assert resp.status_code == 403

    resp = await client.get("/agents", headers=manager_headers(TENANT_A))
    assert resp.status_code == 200


async def test_employee_can_fetch_their_own_agent(client):
    employee_id = uuid.uuid4()
    await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )

    resp = await client.get(
        f"/agents/by-employee/{employee_id}",
        headers=user_headers(TENANT_A, employee_id=employee_id),
    )
    assert resp.status_code == 200
    assert resp.json()["employee_id"] == str(employee_id)


async def test_employee_cannot_fetch_someone_elses_agent(client):
    employee_id = uuid.uuid4()
    await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )

    resp = await client.get(
        f"/agents/by-employee/{employee_id}",
        headers=user_headers(TENANT_A),  # different (random) employee_id, default role
    )
    assert resp.status_code == 403


async def test_manager_can_fetch_anyones_agent(client):
    employee_id = uuid.uuid4()
    await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )

    resp = await client.get(
        f"/agents/by-employee/{employee_id}", headers=manager_headers(TENANT_A)
    )
    assert resp.status_code == 200


async def test_employee_can_update_their_own_agent(client, fake_publisher):
    employee_id = uuid.uuid4()
    resp = await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    agent_id = resp.json()["agent_id"]

    resp = await client.patch(
        f"/agents/{agent_id}",
        json={"temperature": 0.2, "skills": ["calendar", "email"]},
        headers=user_headers(TENANT_A, employee_id=employee_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["temperature"] == 0.2
    assert body["skills"] == ["calendar", "email"]


async def test_manager_cannot_update_someone_elses_agent(client):
    employee_id = uuid.uuid4()
    resp = await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    agent_id = resp.json()["agent_id"]

    resp = await client.patch(
        f"/agents/{agent_id}", json={"temperature": 0.2}, headers=manager_headers(TENANT_A)
    )
    assert resp.status_code == 403  # view-only for a manager; only self or admin can edit


async def test_admin_can_update_anyones_agent(client):
    employee_id = uuid.uuid4()
    resp = await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    agent_id = resp.json()["agent_id"]

    resp = await client.patch(
        f"/agents/{agent_id}", json={"temperature": 0.2}, headers=admin_headers(TENANT_A)
    )
    assert resp.status_code == 200


async def test_update_agent_publishes_audit_event(client, fake_publisher):
    employee_id = uuid.uuid4()
    resp = await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )
    agent_id = resp.json()["agent_id"]

    resp = await client.patch(
        f"/agents/{agent_id}",
        json={"temperature": 0.2},
        headers=user_headers(TENANT_A, employee_id=employee_id),
    )
    assert resp.status_code == 200

    await fake_publisher.wait_for_publish()
    routing_key, payload = fake_publisher.published[0]
    assert routing_key == ROUTING_KEY_AUDIT
    event = AuditEvent.model_validate_json(payload)
    assert event.action == "agent.updated"
    assert event.target_type == "agent"
    assert event.target_id == agent_id


async def test_temperature_out_of_range_is_422(client):
    resp = await client.post(
        "/agents",
        json={"employee_id": str(uuid.uuid4()), "temperature": 1.5},
        headers=system_headers(TENANT_A),
    )
    assert resp.status_code == 422
