import uuid

from auth import encode_access_token, encode_system_token

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()


def system_headers(tenant_id: uuid.UUID) -> dict:
    return {"Authorization": f"Bearer {encode_system_token(tenant_id)}"}


def user_headers(tenant_id: uuid.UUID) -> dict:
    return {"Authorization": f"Bearer {encode_access_token(tenant_id, uuid.uuid4())}"}


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
    assert body["model"] == "claude-sonnet-5"
    assert body["temperature"] == 1.0
    assert body["memory_namespace"] == f"{TENANT_A}:{employee_id}"
    assert body["knowledge_sources"] == []


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

    resp = await client.get(f"/agents/{agent_id}", headers=user_headers(TENANT_B))
    assert resp.status_code == 404

    resp = await client.get("/agents", headers=user_headers(TENANT_B))
    assert resp.json() == []

    resp = await client.get("/agents", headers=user_headers(TENANT_A))
    assert any(a["agent_id"] == agent_id for a in resp.json())


async def test_get_agent_by_employee(client):
    employee_id = uuid.uuid4()
    await client.post(
        "/agents", json={"employee_id": str(employee_id)}, headers=system_headers(TENANT_A)
    )

    resp = await client.get(f"/agents/by-employee/{employee_id}", headers=user_headers(TENANT_A))
    assert resp.status_code == 200
    assert resp.json()["employee_id"] == str(employee_id)


async def test_update_agent(client):
    resp = await client.post(
        "/agents", json={"employee_id": str(uuid.uuid4())}, headers=system_headers(TENANT_A)
    )
    agent_id = resp.json()["agent_id"]

    resp = await client.patch(
        f"/agents/{agent_id}",
        json={"temperature": 0.2, "skills": ["calendar", "email"]},
        headers=user_headers(TENANT_A),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["temperature"] == 0.2
    assert body["skills"] == ["calendar", "email"]


async def test_temperature_out_of_range_is_422(client):
    resp = await client.post(
        "/agents",
        json={"employee_id": str(uuid.uuid4()), "temperature": 1.5},
        headers=system_headers(TENANT_A),
    )
    assert resp.status_code == 422
