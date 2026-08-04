import uuid

import openclaw_runtime.runtime as runtime_module
from openclaw_runtime.agent_client import AgentClientError
from openclaw_runtime.llm_client import LLMClientError

from auth import encode_access_token
from events import ROUTING_KEY_CHAT_INTERACTION, ChatInteractionEvent


def _agent(**overrides) -> dict:
    agent = {
        "agent_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "employee_id": str(uuid.uuid4()),
        "name": "Personal Assistant",
        "personality": None,
        "model": "claude-sonnet-5",
        "temperature": 0.7,
        "prompt": "You are a helpful assistant.",
        "memory_namespace": "ns",
        "knowledge_sources": [],
        "skills": [],
        "permissions": [],
    }
    agent.update(overrides)
    return agent


def _llm_response(**overrides) -> dict:
    response = {
        "content": "Hi there!",
        "model": "claude-sonnet-5",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 5, "output_tokens": 3},
    }
    response.update(overrides)
    return response


def auth_headers() -> tuple[dict, uuid.UUID, uuid.UUID]:
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    token = encode_access_token(tenant_id, employee_id)
    return {"Authorization": f"Bearer {token}"}, tenant_id, employee_id


async def test_successful_chat_publishes_success_event(client, fake_publisher, monkeypatch):
    headers, tenant_id, employee_id = auth_headers()
    agent = _agent()

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    async def fake_generate(**kwargs):
        return _llm_response()

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)

    resp = await client.post("/chat", json={"message": "hi"}, headers=headers)
    assert resp.status_code == 200

    await fake_publisher.wait_for_publish()
    routing_key, payload = fake_publisher.published[0]
    assert routing_key == ROUTING_KEY_CHAT_INTERACTION

    event = ChatInteractionEvent.model_validate_json(payload)
    assert event.tenant_id == tenant_id
    assert event.employee_id == employee_id
    assert event.agent_id == uuid.UUID(agent["agent_id"])
    assert event.success is True
    assert event.error_stage is None
    assert event.latency_ms >= 0


async def test_agent_lookup_failure_publishes_failure_event_with_no_agent_id(
    client, fake_publisher, monkeypatch
):
    headers, tenant_id, employee_id = auth_headers()

    async def fake_get_agent(emp_id, *, bearer_token):
        raise AgentClientError(404, "not found")

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)

    resp = await client.post("/chat", json={"message": "hi"}, headers=headers)
    assert resp.status_code == 404

    await fake_publisher.wait_for_publish()
    event = ChatInteractionEvent.model_validate_json(fake_publisher.published[0][1])
    assert event.success is False
    assert event.error_stage == "agent"
    assert event.agent_id is None


async def test_llm_failure_publishes_failure_event_with_known_agent_id(
    client, fake_publisher, monkeypatch
):
    headers, tenant_id, employee_id = auth_headers()
    agent = _agent()

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    async def fake_generate(**kwargs):
        raise LLMClientError(500, "upstream is on fire")

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)

    resp = await client.post("/chat", json={"message": "hi"}, headers=headers)
    assert resp.status_code == 502

    await fake_publisher.wait_for_publish()
    event = ChatInteractionEvent.model_validate_json(fake_publisher.published[0][1])
    assert event.success is False
    assert event.error_stage == "llm"
    # The agent was fetched successfully before the LLM call failed, so
    # we still know which agent was involved.
    assert event.agent_id == uuid.UUID(agent["agent_id"])


async def test_publish_failure_does_not_break_the_chat_response(
    client, fake_publisher, monkeypatch
):
    headers, _, _ = auth_headers()
    agent = _agent()

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    async def fake_generate(**kwargs):
        return _llm_response(content="all good")

    async def broken_publish(routing_key, payload):
        raise ConnectionError("broker is down")

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)
    monkeypatch.setattr(fake_publisher, "publish", broken_publish)

    resp = await client.post("/chat", json={"message": "hi"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["reply"] == "all good"
