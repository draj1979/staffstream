import uuid

from audit_service.ingestion import handle_audit_event

from auth import encode_access_token
from events import AuditEvent


def admin_headers(tenant_id: uuid.UUID) -> dict:
    token = encode_access_token(tenant_id, uuid.uuid4(), role="admin")
    return {"Authorization": f"Bearer {token}"}


def employee_headers(tenant_id: uuid.UUID) -> dict:
    token = encode_access_token(tenant_id, uuid.uuid4(), role="employee")
    return {"Authorization": f"Bearer {token}"}


async def _seed(tenant_id, **overrides):
    defaults = dict(
        tenant_id=tenant_id,
        actor_employee_id=uuid.uuid4(),
        action="employee.updated",
        target_type="employee",
        target_id=str(uuid.uuid4()),
        metadata={},
    )
    defaults.update(overrides)
    event = AuditEvent(**defaults)
    await handle_audit_event(event.model_dump_json().encode())
    return event


async def test_audit_logs_requires_auth(client):
    resp = await client.get("/audit-logs")
    assert resp.status_code == 401


async def test_audit_logs_requires_admin_role(client):
    tenant_id = uuid.uuid4()
    await _seed(tenant_id)
    resp = await client.get("/audit-logs", headers=employee_headers(tenant_id))
    assert resp.status_code == 403


async def test_admin_can_list_audit_logs(client):
    tenant_id = uuid.uuid4()
    await _seed(tenant_id, action="employee.created")
    await _seed(tenant_id, action="tenant.updated", target_type="tenant", target_id=None)

    resp = await client.get("/audit-logs", headers=admin_headers(tenant_id))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert {row["action"] for row in body} == {"employee.created", "tenant.updated"}


async def test_audit_logs_are_tenant_isolated(client):
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    await _seed(tenant_a)
    await _seed(tenant_b)
    await _seed(tenant_b)

    resp = await client.get("/audit-logs", headers=admin_headers(tenant_a))
    assert len(resp.json()) == 1


async def test_audit_logs_filter_by_action(client):
    tenant_id = uuid.uuid4()
    await _seed(tenant_id, action="employee.created")
    await _seed(tenant_id, action="skill.enablement_changed", target_type="skill")

    resp = await client.get(
        "/audit-logs", params={"action": "employee.created"}, headers=admin_headers(tenant_id)
    )
    body = resp.json()
    assert len(body) == 1
    assert body[0]["action"] == "employee.created"


async def test_audit_logs_filter_by_actor(client):
    tenant_id = uuid.uuid4()
    actor = uuid.uuid4()
    await _seed(tenant_id, actor_employee_id=actor)
    await _seed(tenant_id, actor_employee_id=uuid.uuid4())

    resp = await client.get(
        "/audit-logs",
        params={"actor_employee_id": str(actor)},
        headers=admin_headers(tenant_id),
    )
    body = resp.json()
    assert len(body) == 1
    assert body[0]["actor_employee_id"] == str(actor)


async def test_audit_log_entry_shape_includes_metadata(client):
    tenant_id = uuid.uuid4()
    await _seed(tenant_id, metadata={"old_roles": ["employee"], "new_roles": ["manager"]})

    resp = await client.get("/audit-logs", headers=admin_headers(tenant_id))
    body = resp.json()
    assert body[0]["metadata"] == {"old_roles": ["employee"], "new_roles": ["manager"]}


async def test_no_update_or_delete_routes_exist(client):
    """The service exposes GET only — no route (and therefore no code
    path) is capable of mutating or deleting a stored audit entry."""
    tenant_id = uuid.uuid4()
    await _seed(tenant_id)
    resp = await client.get("/audit-logs", headers=admin_headers(tenant_id))
    entry_id = resp.json()[0]["id"]

    resp_patch = await client.patch(f"/audit-logs/{entry_id}", headers=admin_headers(tenant_id))
    resp_delete = await client.delete(f"/audit-logs/{entry_id}", headers=admin_headers(tenant_id))
    assert resp_patch.status_code == 404
    assert resp_delete.status_code == 404
