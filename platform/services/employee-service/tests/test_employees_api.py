import uuid

TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())


def headers(tenant_id: str) -> dict:
    return {"X-Tenant-Id": tenant_id}


async def test_missing_tenant_header_is_rejected(client):
    resp = await client.get("/employees")
    assert resp.status_code == 400


async def test_create_and_get_employee(client):
    resp = await client.post(
        "/employees",
        json={"email": "ada@acme.com", "department": "Engineering", "roles": ["engineer"]},
        headers=headers(TENANT_A),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tenant_id"] == TENANT_A
    assert body["email"] == "ada@acme.com"

    resp = await client.get(f"/employees/{body['employee_id']}", headers=headers(TENANT_A))
    assert resp.status_code == 200


async def test_employee_isolated_from_other_tenants(client):
    resp = await client.post(
        "/employees", json={"email": "grace@acme.com"}, headers=headers(TENANT_A)
    )
    employee_id = resp.json()["employee_id"]

    # Same employee_id is invisible from a different tenant's context.
    resp = await client.get(f"/employees/{employee_id}", headers=headers(TENANT_B))
    assert resp.status_code == 404

    resp = await client.get("/employees", headers=headers(TENANT_B))
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.get("/employees", headers=headers(TENANT_A))
    assert any(e["employee_id"] == employee_id for e in resp.json())


async def test_manager_must_be_same_tenant(client):
    resp = await client.post(
        "/employees", json={"email": "manager@beta.com"}, headers=headers(TENANT_B)
    )
    other_tenants_manager_id = resp.json()["employee_id"]

    resp = await client.post(
        "/employees",
        json={"email": "report@acme.com", "manager_id": other_tenants_manager_id},
        headers=headers(TENANT_A),
    )
    assert resp.status_code == 400


async def test_manager_in_same_tenant_is_accepted(client):
    resp = await client.post(
        "/employees", json={"email": "boss@acme.com"}, headers=headers(TENANT_A)
    )
    manager_id = resp.json()["employee_id"]

    resp = await client.post(
        "/employees",
        json={"email": "report@acme.com", "manager_id": manager_id},
        headers=headers(TENANT_A),
    )
    assert resp.status_code == 201
    assert resp.json()["manager_id"] == manager_id


async def test_update_employee(client):
    resp = await client.post(
        "/employees", json={"email": "worker@acme.com"}, headers=headers(TENANT_A)
    )
    employee_id = resp.json()["employee_id"]

    resp = await client.patch(
        f"/employees/{employee_id}",
        json={"designation": "Senior Engineer"},
        headers=headers(TENANT_A),
    )
    assert resp.status_code == 200
    assert resp.json()["designation"] == "Senior Engineer"
