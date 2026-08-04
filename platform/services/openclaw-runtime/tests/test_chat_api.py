import uuid

import openclaw_runtime.runtime as runtime_module

from auth import encode_access_token


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


async def test_missing_authorization_header_is_401(client):
    resp = await client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 401


async def test_chat_uses_agent_config_and_returns_reply(client, monkeypatch):
    headers, tenant_id, employee_id = auth_headers()
    agent = _agent(tenant_id=str(tenant_id), employee_id=str(employee_id), temperature=0.3)

    captured = {}

    async def fake_get_agent(emp_id, *, bearer_token):
        assert emp_id == employee_id
        return agent

    async def fake_generate(*, bearer_token, model, system, messages, temperature):
        captured.update(
            bearer_token=bearer_token, model=model, system=system,
            messages=messages, temperature=temperature,
        )
        return _llm_response(content="Sure, here's the answer.")

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)

    resp = await client.post("/chat", json={"message": "what's the weather?"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Sure, here's the answer."
    assert body["agent_id"] == agent["agent_id"]
    assert body["model"] == "claude-sonnet-5"
    assert body["usage"] == {"input_tokens": 5, "output_tokens": 3}

    assert captured["model"] == "claude-sonnet-5"
    assert captured["temperature"] == 0.3
    assert captured["system"] == "You are a helpful assistant."
    assert captured["messages"] == [{"role": "user", "content": "what's the weather?"}]
    assert captured["bearer_token"] == headers["Authorization"]


async def test_personality_is_folded_into_system_prompt(client, monkeypatch):
    headers, _, employee_id = auth_headers()
    agent = _agent(personality="Terse and dry-witted.")

    captured = {}

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    async def fake_generate(**kwargs):
        captured.update(kwargs)
        return _llm_response()

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)

    resp = await client.post("/chat", json={"message": "hi"}, headers=headers)
    assert resp.status_code == 200
    assert "Terse and dry-witted." in captured["system"]


async def test_no_in_process_caching_of_agent_config(client, monkeypatch):
    """Two calls, two different agent configs from Agent Registry — proves
    OpenClaw doesn't cache the agent between requests."""
    headers, _, employee_id = auth_headers()
    agents = [_agent(model="claude-haiku-4-5-20251001"), _agent(model="claude-opus-4-8")]
    calls = {"n": 0}

    async def fake_get_agent(emp_id, *, bearer_token):
        agent = agents[calls["n"]]
        calls["n"] += 1
        return agent

    seen_models = []

    async def fake_generate(*, model, **kwargs):
        seen_models.append(model)
        return _llm_response(model=model)

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)

    resp1 = await client.post("/chat", json={"message": "first"}, headers=headers)
    resp2 = await client.post("/chat", json={"message": "second"}, headers=headers)

    assert resp1.json()["model"] == "claude-haiku-4-5-20251001"
    assert resp2.json()["model"] == "claude-opus-4-8"
    assert seen_models == ["claude-haiku-4-5-20251001", "claude-opus-4-8"]


async def test_missing_agent_returns_404(client, monkeypatch):
    headers, _, _ = auth_headers()

    from openclaw_runtime.agent_client import AgentClientError

    async def fake_get_agent(emp_id, *, bearer_token):
        raise AgentClientError(404, "not found")

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)

    resp = await client.post("/chat", json={"message": "hi"}, headers=headers)
    assert resp.status_code == 404


async def test_llm_gateway_failure_returns_502(client, monkeypatch):
    headers, _, _ = auth_headers()
    agent = _agent()

    from openclaw_runtime.llm_client import LLMClientError

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    async def fake_generate(**kwargs):
        raise LLMClientError(500, "upstream is on fire")

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)

    resp = await client.post("/chat", json={"message": "hi"}, headers=headers)
    assert resp.status_code == 502
