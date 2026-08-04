import uuid
from datetime import UTC, datetime, timedelta

from analytics_service.ingestion import handle_chat_interaction_event, handle_llm_usage_event

from auth import encode_access_token
from events import ChatInteractionEvent, LLMUsageEvent


def headers(tenant_id: uuid.UUID) -> dict:
    token = encode_access_token(tenant_id, uuid.uuid4())
    return {"Authorization": f"Bearer {token}"}


async def _seed_llm_usage(tenant_id, **overrides):
    defaults = dict(
        tenant_id=tenant_id,
        employee_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        provider="anthropic",
        model="claude-sonnet-5",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01,
    )
    defaults.update(overrides)
    event = LLMUsageEvent(**defaults)
    await handle_llm_usage_event(event.model_dump_json().encode())
    return event


async def _seed_chat_interaction(tenant_id, **overrides):
    defaults = dict(
        tenant_id=tenant_id,
        employee_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        success=True,
        error_stage=None,
        latency_ms=100,
    )
    defaults.update(overrides)
    event = ChatInteractionEvent(**defaults)
    await handle_chat_interaction_event(event.model_dump_json().encode())
    return event


async def test_admin_dashboard_requires_auth(client):
    resp = await client.get("/analytics/admin")
    assert resp.status_code == 401


async def test_admin_dashboard_aggregates_conversations_and_tokens(client):
    tenant_id = uuid.uuid4()
    await _seed_chat_interaction(tenant_id, success=True)
    await _seed_chat_interaction(tenant_id, success=False)
    await _seed_llm_usage(tenant_id, input_tokens=100, output_tokens=50, cost_usd=0.01)
    await _seed_llm_usage(tenant_id, input_tokens=200, output_tokens=75, cost_usd=0.02)

    resp = await client.get("/analytics/admin", headers=headers(tenant_id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_conversations"] == 2
    assert body["success_rate"] == 0.5
    assert body["total_input_tokens"] == 300
    assert body["total_output_tokens"] == 125
    assert round(body["total_cost_usd"], 4) == 0.03


async def test_admin_dashboard_is_tenant_isolated(client):
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    await _seed_chat_interaction(tenant_a, success=True)
    await _seed_chat_interaction(tenant_b, success=True)
    await _seed_chat_interaction(tenant_b, success=True)

    resp = await client.get("/analytics/admin", headers=headers(tenant_a))
    assert resp.json()["total_conversations"] == 1


async def test_admin_dashboard_excludes_events_outside_date_range(client):
    tenant_id = uuid.uuid4()
    old = datetime.now(UTC) - timedelta(days=60)
    await _seed_chat_interaction(tenant_id, success=True, created_at=old)

    resp = await client.get("/analytics/admin", headers=headers(tenant_id))
    assert resp.json()["total_conversations"] == 0

    from_date = (old - timedelta(days=1)).date().isoformat()
    to_date = (old + timedelta(days=1)).date().isoformat()
    resp = await client.get(
        f"/analytics/admin?from_date={from_date}&to_date={to_date}",
        headers=headers(tenant_id),
    )
    assert resp.json()["total_conversations"] == 1


async def test_finance_dashboard_breaks_down_cost_by_model_and_employee(client):
    tenant_id = uuid.uuid4()
    employee_id = uuid.uuid4()
    await _seed_llm_usage(
        tenant_id, employee_id=employee_id, model="claude-sonnet-5", cost_usd=0.05
    )
    await _seed_llm_usage(
        tenant_id, employee_id=employee_id, model="claude-haiku-4-5-20251001", cost_usd=0.01
    )

    resp = await client.get("/analytics/finance", headers=headers(tenant_id))
    assert resp.status_code == 200
    body = resp.json()
    assert round(body["total_cost_usd"], 4) == 0.06
    models = {m["model"] for m in body["cost_by_model"]}
    assert models == {"claude-sonnet-5", "claude-haiku-4-5-20251001"}
    assert body["cost_by_employee"][0]["employee_id"] == str(employee_id)
    assert len(body["daily_cost"]) >= 1


async def test_it_dashboard_computes_error_rate_and_latency(client):
    tenant_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    await _seed_chat_interaction(
        tenant_id, agent_id=agent_id, success=True, latency_ms=100
    )
    await _seed_chat_interaction(
        tenant_id, agent_id=agent_id, success=True, latency_ms=200
    )
    await _seed_chat_interaction(
        tenant_id,
        agent_id=agent_id,
        success=False,
        error_stage="llm",
        latency_ms=900,
    )

    resp = await client.get("/analytics/it", headers=headers(tenant_id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_requests"] == 3
    assert round(body["error_rate"], 4) == round(1 / 3, 4)
    assert body["avg_latency_ms"] == (100 + 200 + 900) / 3
    assert body["requests_by_agent"][0]["agent_id"] == str(agent_id)
    assert body["requests_by_agent"][0]["request_count"] == 3
    assert body["errors_by_stage"] == [{"error_stage": "llm", "count": 1}]
