import uuid

from auth import encode_access_token, encode_system_token
from events import ROUTING_KEY_AUDIT, AuditEvent


def system_headers(tenant_id: uuid.UUID) -> dict:
    return {"Authorization": f"Bearer {encode_system_token(tenant_id)}"}


def user_headers(tenant_id: uuid.UUID) -> dict:
    return {"Authorization": f"Bearer {encode_access_token(tenant_id, uuid.uuid4())}"}


def admin_headers(tenant_id: uuid.UUID) -> dict:
    return {"Authorization": f"Bearer {encode_access_token(tenant_id, uuid.uuid4(), role='admin')}"}


async def test_create_tenant_requires_no_auth(client):
    resp = await client.post(
        "/tenants",
        json={"company_name": "Acme Corp", "plan": "business", "storage_quota_bytes": 1_000_000},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["company_name"] == "Acme Corp"
    assert body["subscription_status"] == "trial"


async def test_get_tenant_requires_auth(client):
    resp = await client.post("/tenants", json={"company_name": "Acme Corp"})
    tenant_id = resp.json()["tenant_id"]

    resp = await client.get(f"/tenants/{tenant_id}")
    assert resp.status_code == 401


async def test_get_own_tenant_succeeds(client):
    resp = await client.post("/tenants", json={"company_name": "Acme Corp"})
    tenant_id = resp.json()["tenant_id"]

    resp = await client.get(f"/tenants/{tenant_id}", headers=user_headers(uuid.UUID(tenant_id)))
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == tenant_id


async def test_get_other_tenant_is_forbidden(client):
    resp = await client.post("/tenants", json={"company_name": "Acme Corp"})
    tenant_id = resp.json()["tenant_id"]

    resp = await client.get(f"/tenants/{tenant_id}", headers=user_headers(uuid.uuid4()))
    assert resp.status_code == 403


async def test_get_missing_tenant_404s(client):
    tenant_id = uuid.uuid4()
    resp = await client.get(f"/tenants/{tenant_id}", headers=user_headers(tenant_id))
    assert resp.status_code == 404


async def test_list_requires_system_scope(client):
    await client.post("/tenants", json={"company_name": "Globex"})

    resp = await client.get("/tenants")
    assert resp.status_code == 401

    resp = await client.get("/tenants", headers=user_headers(uuid.uuid4()))
    assert resp.status_code == 403

    resp = await client.get("/tenants", headers=system_headers(uuid.uuid4()))
    assert resp.status_code == 200


async def test_update_own_tenant_requires_admin_role(client):
    resp = await client.post("/tenants", json={"company_name": "Globex"})
    tenant_id = resp.json()["tenant_id"]

    resp = await client.patch(
        f"/tenants/{tenant_id}",
        json={"subscription_status": "active"},
        headers=user_headers(uuid.UUID(tenant_id)),
    )
    assert resp.status_code == 403  # default "employee" role can't change tenant settings


async def test_admin_can_update_own_tenant(client):
    resp = await client.post("/tenants", json={"company_name": "Globex"})
    tenant_id = resp.json()["tenant_id"]

    resp = await client.patch(
        f"/tenants/{tenant_id}",
        json={"subscription_status": "active"},
        headers=admin_headers(uuid.UUID(tenant_id)),
    )
    assert resp.status_code == 200
    assert resp.json()["subscription_status"] == "active"


async def test_update_other_tenant_is_forbidden_even_for_admin(client):
    resp = await client.post("/tenants", json={"company_name": "Globex"})
    tenant_id = resp.json()["tenant_id"]

    resp = await client.patch(
        f"/tenants/{tenant_id}",
        json={"subscription_status": "active"},
        headers=admin_headers(uuid.uuid4()),
    )
    assert resp.status_code == 403


async def test_admin_update_publishes_audit_event(client, fake_publisher):
    resp = await client.post("/tenants", json={"company_name": "Globex"})
    tenant_id = resp.json()["tenant_id"]

    resp = await client.patch(
        f"/tenants/{tenant_id}",
        json={"subscription_status": "active"},
        headers=admin_headers(uuid.UUID(tenant_id)),
    )
    assert resp.status_code == 200

    await fake_publisher.wait_for_publish()
    routing_key, payload = fake_publisher.published[0]
    assert routing_key == ROUTING_KEY_AUDIT
    event = AuditEvent.model_validate_json(payload)
    assert event.action == "tenant.updated"
    assert event.target_type == "tenant"
    assert event.target_id == tenant_id
    assert event.metadata == {"subscription_status": "active"}
