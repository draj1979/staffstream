async def test_create_and_get_tenant(client):
    resp = await client.post(
        "/tenants",
        json={"company_name": "Acme Corp", "plan": "business", "storage_quota_bytes": 1_000_000},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["company_name"] == "Acme Corp"
    assert body["subscription_status"] == "trial"

    tenant_id = body["tenant_id"]
    resp = await client.get(f"/tenants/{tenant_id}")
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == tenant_id


async def test_get_missing_tenant_404s(client):
    resp = await client.get("/tenants/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_list_and_update_tenant(client):
    resp = await client.post("/tenants", json={"company_name": "Globex"})
    tenant_id = resp.json()["tenant_id"]

    resp = await client.get("/tenants")
    assert resp.status_code == 200
    assert any(t["tenant_id"] == tenant_id for t in resp.json())

    resp = await client.patch(f"/tenants/{tenant_id}", json={"subscription_status": "active"})
    assert resp.status_code == 200
    assert resp.json()["subscription_status"] == "active"
