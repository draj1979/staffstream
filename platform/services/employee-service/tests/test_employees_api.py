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


def admin_headers(tenant_id: uuid.UUID, employee_id: uuid.UUID | None = None) -> dict:
    return user_headers(tenant_id, employee_id, role="admin")


def manager_headers(tenant_id: uuid.UUID, employee_id: uuid.UUID) -> dict:
    return user_headers(tenant_id, employee_id, role="manager")


async def test_missing_authorization_header_is_401(client):
    resp = await client.get("/employees")
    assert resp.status_code == 401


async def test_create_employee_with_system_token_bootstrap(client, fake_agent_registry):
    resp = await client.post(
        "/employees",
        json={"email": "ada@acme.com", "department": "Engineering", "roles": ["engineer"]},
        headers=system_headers(TENANT_A),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tenant_id"] == str(TENANT_A)
    assert body["email"] == "ada@acme.com"
    assert body["employee_id"] in fake_agent_registry  # default agent was auto-created
    assert body["agent_id"] == fake_agent_registry[body["employee_id"]]["agent_id"]

    resp = await client.get(f"/employees/{body['employee_id']}", headers=user_headers(TENANT_A))
    assert resp.status_code == 200


async def test_agent_registry_failure_surfaces_as_502(client, monkeypatch):
    from employee_service.agent_registry_client import AgentRegistryError

    async def failing_create_default_agent(tenant_id, *, employee_id):
        raise AgentRegistryError(500, "agent registry is down")

    monkeypatch.setattr(
        "employee_service.routers.employees.create_default_agent", failing_create_default_agent
    )

    resp = await client.post(
        "/employees", json={"email": "unlucky@acme.com"}, headers=system_headers(TENANT_A)
    )
    assert resp.status_code == 502


async def test_create_employee_with_plain_employee_token_is_forbidden(client):
    resp = await client.post(
        "/employees",
        json={"email": "logged-in@acme.com"},
        headers=user_headers(TENANT_A),  # default "employee" role
    )
    assert resp.status_code == 403


async def test_create_employee_with_admin_token_works(client):
    resp = await client.post(
        "/employees",
        json={"email": "logged-in-admin@acme.com"},
        headers=admin_headers(TENANT_A),
    )
    assert resp.status_code == 201


async def test_manager_can_only_create_employees_in_own_department(client):
    manager_id = uuid.uuid4()
    resp = await client.post(
        "/employees",
        json={"email": "same-dept@acme.com", "department": "Engineering"},
        headers=manager_headers(TENANT_A, manager_id),
    )
    # the manager token's own employee row doesn't exist in this fresh DB,
    # so their "own department" resolves to None — matching None here
    resp2 = await client.post(
        "/employees",
        json={"email": "no-dept@acme.com", "department": None},
        headers=manager_headers(TENANT_A, manager_id),
    )
    assert resp.status_code == 403  # manager's own department (None) != "Engineering"
    assert resp2.status_code == 201


async def test_system_token_rejected_on_list_route(client):
    resp = await client.get("/employees", headers=system_headers(TENANT_A))
    assert resp.status_code == 403


async def test_system_token_accepted_on_get_by_id(client):
    """Auth Service's login/refresh/SSO-callback role lookup calls this
    route with a system token — it has to work without a live employee
    session, same reasoning as the by-email route."""
    resp = await client.post(
        "/employees", json={"email": "worker@acme.com"}, headers=system_headers(TENANT_A)
    )
    employee_id = resp.json()["employee_id"]

    resp = await client.get(f"/employees/{employee_id}", headers=system_headers(TENANT_A))
    assert resp.status_code == 200
    assert resp.json()["employee_id"] == employee_id


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


async def test_update_employee_requires_manager_or_admin(client):
    resp = await client.post(
        "/employees", json={"email": "worker@acme.com"}, headers=system_headers(TENANT_A)
    )
    employee_id = resp.json()["employee_id"]

    resp = await client.patch(
        f"/employees/{employee_id}",
        json={"designation": "Senior Engineer"},
        headers=user_headers(TENANT_A),  # default "employee" role
    )
    assert resp.status_code == 403

    resp = await client.patch(
        f"/employees/{employee_id}",
        json={"designation": "Senior Engineer"},
        headers=admin_headers(TENANT_A),
    )
    assert resp.status_code == 200
    assert resp.json()["designation"] == "Senior Engineer"


async def test_manager_can_only_update_employees_in_own_department(client):
    resp = await client.post(
        "/employees",
        json={"email": "manager@acme.com", "department": "Sales"},
        headers=system_headers(TENANT_A),
    )
    manager_id = uuid.UUID(resp.json()["employee_id"])
    resp = await client.patch(
        f"/employees/{manager_id}",
        json={"roles": ["manager"]},
        headers=admin_headers(TENANT_A),
    )
    assert resp.status_code == 200  # give the manager their role via an admin first

    resp = await client.post(
        "/employees",
        json={"email": "same-dept@acme.com", "department": "Sales"},
        headers=system_headers(TENANT_A),
    )
    same_dept_id = resp.json()["employee_id"]

    resp = await client.post(
        "/employees",
        json={"email": "other-dept@acme.com", "department": "Engineering"},
        headers=system_headers(TENANT_A),
    )
    other_dept_id = resp.json()["employee_id"]

    resp = await client.patch(
        f"/employees/{same_dept_id}",
        json={"designation": "Account Executive"},
        headers=manager_headers(TENANT_A, manager_id),
    )
    assert resp.status_code == 200

    resp = await client.patch(
        f"/employees/{other_dept_id}",
        json={"designation": "Senior Engineer"},
        headers=manager_headers(TENANT_A, manager_id),
    )
    assert resp.status_code == 403


async def test_manager_cannot_change_department(client):
    resp = await client.post(
        "/employees",
        json={"email": "mgr@acme.com", "department": "Sales"},
        headers=system_headers(TENANT_A),
    )
    manager_id = uuid.UUID(resp.json()["employee_id"])

    resp = await client.post(
        "/employees",
        json={"email": "report@acme.com", "department": "Sales"},
        headers=system_headers(TENANT_A),
    )
    report_id = resp.json()["employee_id"]

    resp = await client.patch(
        f"/employees/{report_id}",
        json={"department": "Engineering"},
        headers=manager_headers(TENANT_A, manager_id),
    )
    assert resp.status_code == 403


async def test_only_admin_can_change_roles(client):
    resp = await client.post(
        "/employees",
        json={"email": "mgr@acme.com", "department": "Sales"},
        headers=system_headers(TENANT_A),
    )
    manager_id = resp.json()["employee_id"]

    resp = await client.post(
        "/employees",
        json={"email": "report@acme.com", "department": "Sales"},
        headers=system_headers(TENANT_A),
    )
    report_id = resp.json()["employee_id"]

    resp = await client.patch(
        f"/employees/{report_id}",
        json={"roles": ["manager"]},
        headers=manager_headers(TENANT_A, uuid.UUID(manager_id)),
    )
    assert resp.status_code == 403

    resp = await client.patch(
        f"/employees/{report_id}",
        json={"roles": ["manager"]},
        headers=admin_headers(TENANT_A),
    )
    assert resp.status_code == 200
    assert resp.json()["roles"] == ["manager"]


async def test_update_publishes_audit_events_including_role_change(client, fake_publisher):
    resp = await client.post(
        "/employees", json={"email": "worker@acme.com"}, headers=system_headers(TENANT_A)
    )
    employee_id = resp.json()["employee_id"]

    resp = await client.patch(
        f"/employees/{employee_id}",
        json={"roles": ["manager"]},
        headers=admin_headers(TENANT_A),
    )
    assert resp.status_code == 200

    await fake_publisher.wait_for_publish()
    events = [
        AuditEvent.model_validate_json(payload)
        for routing_key, payload in fake_publisher.published
        if routing_key == ROUTING_KEY_AUDIT
    ]
    actions = {e.action for e in events}
    assert "employee.updated" in actions
    assert "employee.role_changed" in actions
    role_change = next(e for e in events if e.action == "employee.role_changed")
    assert role_change.metadata == {"old_roles": [], "new_roles": ["manager"]}


async def test_create_publishes_audit_event(client, fake_publisher):
    resp = await client.post(
        "/employees", json={"email": "new-hire@acme.com"}, headers=system_headers(TENANT_A)
    )
    employee_id = resp.json()["employee_id"]

    await fake_publisher.wait_for_publish()
    routing_key, payload = fake_publisher.published[0]
    assert routing_key == ROUTING_KEY_AUDIT
    event = AuditEvent.model_validate_json(payload)
    assert event.action == "employee.created"
    assert event.target_id == employee_id


async def test_get_employee_by_email(client):
    resp = await client.post(
        "/employees", json={"email": "findme@acme.com"}, headers=system_headers(TENANT_A)
    )
    employee_id = resp.json()["employee_id"]

    resp = await client.get(
        "/employees/by-email/findme@acme.com", headers=system_headers(TENANT_A)
    )
    assert resp.status_code == 200
    assert resp.json()["employee_id"] == employee_id


async def test_get_employee_by_email_not_found(client):
    resp = await client.get(
        "/employees/by-email/nobody@acme.com", headers=system_headers(TENANT_A)
    )
    assert resp.status_code == 404
