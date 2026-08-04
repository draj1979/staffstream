import uuid

from auth import encode_access_token
from events import ROUTING_KEY_LLM_USAGE, LLMUsageEvent


def user_headers(tenant_id: uuid.UUID, employee_id: uuid.UUID) -> dict:
    token = encode_access_token(tenant_id, employee_id)
    return {"Authorization": f"Bearer {token}"}


async def test_successful_generate_publishes_usage_event(client, fake_publisher):
    tenant_id, employee_id, agent_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    resp = await client.post(
        "/generate",
        json={
            "model": "claude-sonnet-5",
            "messages": [{"role": "user", "content": "hi"}],
            "agent_id": str(agent_id),
        },
        headers=user_headers(tenant_id, employee_id),
    )
    assert resp.status_code == 200

    await fake_publisher.wait_for_publish()
    assert len(fake_publisher.published) == 1
    routing_key, payload = fake_publisher.published[0]
    assert routing_key == ROUTING_KEY_LLM_USAGE

    event = LLMUsageEvent.model_validate_json(payload)
    assert event.tenant_id == tenant_id
    assert event.employee_id == employee_id
    assert event.agent_id == agent_id
    assert event.provider == "claude"
    assert event.model == "claude-sonnet-5"
    assert event.input_tokens == 3
    assert event.output_tokens == 5
    assert event.cost_usd > 0


async def test_usage_event_agent_id_is_none_when_not_supplied(client, fake_publisher):
    resp = await client.post(
        "/generate",
        json={"model": "claude-sonnet-5", "messages": [{"role": "user", "content": "hi"}]},
        headers=user_headers(uuid.uuid4(), uuid.uuid4()),
    )
    assert resp.status_code == 200

    await fake_publisher.wait_for_publish()
    _, payload = fake_publisher.published[0]
    assert LLMUsageEvent.model_validate_json(payload).agent_id is None


async def test_publish_failure_does_not_break_the_response(client, fake_publisher, monkeypatch):
    async def broken_publish(routing_key, payload):
        raise ConnectionError("broker is down")

    monkeypatch.setattr(fake_publisher, "publish", broken_publish)

    resp = await client.post(
        "/generate",
        json={"model": "claude-sonnet-5", "messages": [{"role": "user", "content": "hi"}]},
        headers=user_headers(uuid.uuid4(), uuid.uuid4()),
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "echo: hi"


async def test_unknown_provider_does_not_publish_a_usage_event(client, fake_publisher):
    resp = await client.post(
        "/generate",
        json={
            "model": "gpt-5",
            "provider": "openai",
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers=user_headers(uuid.uuid4(), uuid.uuid4()),
    )
    assert resp.status_code == 400
    assert fake_publisher.published == []
