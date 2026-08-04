import uuid

from auth import encode_access_token

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()
NAMESPACE = f"{TENANT_A}:{uuid.uuid4()}"


def headers(tenant_id: uuid.UUID) -> dict:
    token = encode_access_token(tenant_id, uuid.uuid4())
    return {"Authorization": f"Bearer {token}"}


async def test_missing_authorization_header_is_401(client):
    resp = await client.get(f"/memory/{NAMESPACE}/conversation")
    assert resp.status_code == 401


async def test_conversation_turns_are_returned_in_chronological_order(client):
    h = headers(TENANT_A)
    for role, content in [("user", "hi"), ("assistant", "hello!"), ("user", "how are you?")]:
        resp = await client.post(
            f"/memory/{NAMESPACE}/conversation",
            json={"role": role, "content": content},
            headers=h,
        )
        assert resp.status_code == 201

    resp = await client.get(f"/memory/{NAMESPACE}/conversation", headers=h)
    assert resp.status_code == 200
    turns = resp.json()
    assert [t["content"] for t in turns] == ["hi", "hello!", "how are you?"]
    assert [t["role"] for t in turns] == ["user", "assistant", "user"]


async def test_conversation_history_respects_limit(client):
    h = headers(TENANT_A)
    ns = f"{TENANT_A}:{uuid.uuid4()}"
    for i in range(5):
        await client.post(
            f"/memory/{ns}/conversation", json={"role": "user", "content": str(i)}, headers=h
        )

    resp = await client.get(f"/memory/{ns}/conversation?limit=2", headers=h)
    turns = resp.json()
    assert [t["content"] for t in turns] == ["3", "4"]  # most recent 2, oldest first


async def test_long_term_memory_add_and_list(client):
    h = headers(TENANT_A)
    ns = f"{TENANT_A}:{uuid.uuid4()}"
    resp = await client.post(
        f"/memory/{ns}/long-term", json={"content": "likes async work"}, headers=h
    )
    assert resp.status_code == 201

    resp = await client.get(f"/memory/{ns}/long-term", headers=h)
    assert resp.status_code == 200
    assert resp.json()[0]["content"] == "likes async work"


async def test_preferences_upsert_and_get(client):
    h = headers(TENANT_A)
    ns = f"{TENANT_A}:{uuid.uuid4()}"

    resp = await client.put(f"/memory/{ns}/preferences/tone", json={"value": "formal"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["value"] == "formal"

    resp = await client.put(f"/memory/{ns}/preferences/tone", json={"value": "casual"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["value"] == "casual"

    resp = await client.get(f"/memory/{ns}/preferences", headers=h)
    prefs = resp.json()
    assert len(prefs) == 1  # upserted, not duplicated
    assert prefs[0]["key"] == "tone"
    assert prefs[0]["value"] == "casual"


async def test_preference_delete(client):
    h = headers(TENANT_A)
    ns = f"{TENANT_A}:{uuid.uuid4()}"
    await client.put(f"/memory/{ns}/preferences/tone", json={"value": "formal"}, headers=h)

    resp = await client.delete(f"/memory/{ns}/preferences/tone", headers=h)
    assert resp.status_code == 204

    resp = await client.get(f"/memory/{ns}/preferences", headers=h)
    assert resp.json() == []

    resp = await client.delete(f"/memory/{ns}/preferences/tone", headers=h)
    assert resp.status_code == 404


async def test_learned_facts_add_and_list(client):
    h = headers(TENANT_A)
    ns = f"{TENANT_A}:{uuid.uuid4()}"
    resp = await client.post(
        f"/memory/{ns}/facts", json={"content": "always asks for a summary first"}, headers=h
    )
    assert resp.status_code == 201

    resp = await client.get(f"/memory/{ns}/facts", headers=h)
    assert resp.json()[0]["content"] == "always asks for a summary first"


async def test_cross_tenant_isolation_even_with_same_namespace_string(client):
    """The namespace string is just a partition key for app-level queries —
    tenant_id is the real isolation boundary. Even if two tenants somehow
    used the identical namespace string, tenant B must never see tenant
    A's rows."""
    shared_namespace = "collision-prone-namespace"
    a_headers, b_headers = headers(TENANT_A), headers(TENANT_B)

    await client.post(
        f"/memory/{shared_namespace}/conversation",
        json={"role": "user", "content": "tenant A's secret"},
        headers=a_headers,
    )

    resp = await client.get(f"/memory/{shared_namespace}/conversation", headers=b_headers)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.get(f"/memory/{shared_namespace}/conversation", headers=a_headers)
    assert len(resp.json()) == 1
