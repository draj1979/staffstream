import uuid

from auth import encode_access_token, encode_system_token

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()


def system_headers(tenant_id: uuid.UUID) -> dict:
    return {"Authorization": f"Bearer {encode_system_token(tenant_id)}"}


def user_headers(tenant_id: uuid.UUID, employee_id: uuid.UUID | None = None) -> dict:
    token = encode_access_token(tenant_id, employee_id or uuid.uuid4())
    return {"Authorization": f"Bearer {token}"}


async def test_missing_authorization_header_is_401(client):
    resp = await client.get("/employees")
    assert resp.status_code == 401


async def test_create_employee_with_system_token_bootstrap(client):
    resp = await client.post(
        "/employees",
        json={"email": "ada@acme.com", "department": "Engineering", "roles": ["engineer"]},
        headers=system_headers(TENANT_A),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tenant_id"] == str(TENANT_A)
    assert body["email"] == "ada@acme.com"

    resp = await client.get(f"/employees/{body['employee_id']}", headers=user_headers(TENANT_A))
    assert resp.status_code == 200


async def test_create_employee_with_user_token_also_works(client):
    resp = await client.post(
        "/employees",
        json={"email": "logged-in-admin@acme.com"},
        headers=user_headers(TENANT_A),
    )
    assert resp.status_code == 201


async def test_system_token_rejected_on_read_routes(client):
    resp = await client.get("/employees", headers=system_headers(TENANT_A))
    assert resp.status_code == 403


async def test_employee_isolated_from_other_tenants(client):
    resp = await client.post(
        "/employees", json={"email": "grace@acme.com"}, headers=system_headers(TENANT_A)
    )
    employee_id = resp.json()["employee_id"]

    # Same employee_id is invisible from a different tenant's context.
    resp = await client.get(f"/employees/{employee_id}", headers=user_headers(TENANT_B))
    assert resp.status_code == 404

    resp = await client.get("/employees", headers=user_headers(TENANT_B))
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.get("/employees", headers=user_headers(TENANT_A))
    assert any(e["employee_id"] == employee_id for e in resp.json())


async def test_manager_must_be_same_tenant(client):
    resp = await client.post(
        "/employees", json={"email": "manager@beta.com"}, headers=system_headers(TENANT_B)
    )
    other_tenants_manager_id = resp.json()["employee_id"]

    resp = await client.post(
        "/employees",
        json={"email": "report@acme.com", "manager_id": other_tenants_manager_id},
        headers=system_headers(TENANT_A),
    )
    assert resp.status_code == 400


async def test_manager_in_same_tenant_is_accepted(client):
    resp = await client.post(
        "/employees", json={"email": "boss@acme.com"}, headers=system_headers(TENANT_A)
    )
    manager_id = resp.json()["employee_id"]

    resp = await client.post(
        "/employees",
        json={"email": "report@acme.com", "manager_id": manager_id},
        headers=system_headers(TENANT_A),
    )
    assert resp.status_code == 201
    assert resp.json()["manager_id"] == manager_id


async def test_update_employee(client):
    resp = await client.post(
        "/employees", json={"email": "worker@acme.com"}, headers=system_headers(TENANT_A)
    )
    employee_id = resp.json()["employee_id"]

    resp = await client.patch(
        f"/employees/{employee_id}",
        json={"designation": "Senior Engineer"},
        headers=user_headers(TENANT_A),
    )
    assert resp.status_code == 200
    assert resp.json()["designation"] == "Senior Engineer"
