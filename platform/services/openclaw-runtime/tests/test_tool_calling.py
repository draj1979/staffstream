import json
import uuid

import openclaw_runtime.runtime as runtime_module
from openclaw_runtime import skill_client as skill_client_module
from openclaw_runtime.skill_client import SkillClientError

from auth import encode_access_token
from events import ROUTING_KEY_SKILL_USAGE, SkillUsageEvent


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
        "tool_calls": [],
    }
    response.update(overrides)
    return response


def auth_headers() -> tuple[dict, uuid.UUID, uuid.UUID]:
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    token = encode_access_token(tenant_id, employee_id)
    return {"Authorization": f"Bearer {token}"}, tenant_id, employee_id


def _tool_use_response(**overrides) -> dict:
    response = {
        "content": "Let me check Slack for you.",
        "model": "claude-sonnet-5",
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 20, "output_tokens": 15},
        "tool_calls": [
            {
                "id": "toolu_1",
                "name": "slack_post_message",
                "input": {"channel_id": "C1", "text": "hi"},
            }
        ],
    }
    response.update(overrides)
    return response


async def _fake_list_tools(*, bearer_token):
    return [
        {
            "skill_id": "slack",
            "name": "slack_post_message",
            "description": "Post a message",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]


async def test_agent_without_skills_never_calls_skill_marketplace(client, monkeypatch):
    """agent.skills is empty by default — Load Skills should short-circuit
    before ever making an HTTP call, and no `tools` param should reach the
    LLM Gateway."""
    headers, tenant_id, employee_id = auth_headers()
    agent = _agent(tenant_id=str(tenant_id), employee_id=str(employee_id))

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    called = {"list_tools": False}

    async def fake_list_tools(*, bearer_token):
        called["list_tools"] = True
        return []

    captured = {}

    async def fake_generate(**kwargs):
        captured.update(kwargs)
        return _llm_response()

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)
    monkeypatch.setattr(skill_client_module, "list_tools", fake_list_tools)

    resp = await client.post("/chat", json={"message": "hi"}, headers=headers)
    assert resp.status_code == 200
    assert called["list_tools"] is False
    assert captured["tools"] is None


async def test_tool_call_loop_invokes_skill_and_returns_final_reply(client, monkeypatch):
    headers, tenant_id, employee_id = auth_headers()
    agent = _agent(tenant_id=str(tenant_id), employee_id=str(employee_id), skills=["slack"])

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    generate_calls = []

    async def fake_generate(**kwargs):
        generate_calls.append(kwargs)
        if len(generate_calls) == 1:
            return _tool_use_response()
        return _llm_response(content="Done — I posted it to #general.")

    invoke_calls = []

    async def fake_invoke_skill(skill_id, *, tool_name, tool_input, bearer_token):
        invoke_calls.append((skill_id, tool_name, tool_input))
        return {"ok": True, "ts": "123.456"}

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)
    monkeypatch.setattr(skill_client_module, "list_tools", _fake_list_tools)
    monkeypatch.setattr(runtime_module, "invoke_skill", fake_invoke_skill)

    resp = await client.post(
        "/chat", json={"message": "post hi to #general"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Done — I posted it to #general."
    # usage is summed across both LLM calls in the turn
    assert body["usage"] == {"input_tokens": 25, "output_tokens": 18}

    assert invoke_calls == [("slack", "slack_post_message", {"channel_id": "C1", "text": "hi"})]

    # second generate() call includes the assistant tool_use echo-back and
    # the tool_result — this is what makes the follow-up turn valid
    # Anthropic input.
    second_call_messages = generate_calls[1]["messages"]
    assistant_msg = next(m for m in second_call_messages if m["role"] == "assistant")
    assert any(block["type"] == "tool_use" for block in assistant_msg["content"])
    tool_result_msg = second_call_messages[-1]
    assert tool_result_msg["role"] == "user"
    assert tool_result_msg["content"][0]["type"] == "tool_result"
    assert tool_result_msg["content"][0]["tool_use_id"] == "toolu_1"
    assert json.loads(tool_result_msg["content"][0]["content"]) == {"ok": True, "ts": "123.456"}


async def test_tool_call_publishes_skill_usage_event(client, monkeypatch, fake_publisher):
    headers, tenant_id, employee_id = auth_headers()
    agent = _agent(tenant_id=str(tenant_id), employee_id=str(employee_id), skills=["slack"])

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    generate_calls = []

    async def fake_generate(**kwargs):
        generate_calls.append(kwargs)
        if len(generate_calls) == 1:
            return _tool_use_response()
        return _llm_response()

    async def fake_invoke_skill(skill_id, *, tool_name, tool_input, bearer_token):
        return {"ok": True}

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)
    monkeypatch.setattr(skill_client_module, "list_tools", _fake_list_tools)
    monkeypatch.setattr(runtime_module, "invoke_skill", fake_invoke_skill)

    resp = await client.post("/chat", json={"message": "post hi"}, headers=headers)
    assert resp.status_code == 200

    await fake_publisher.wait_for_publish()
    skill_events = [
        SkillUsageEvent.model_validate_json(payload)
        for routing_key, payload in fake_publisher.published
        if routing_key == ROUTING_KEY_SKILL_USAGE
    ]
    assert len(skill_events) == 1
    assert skill_events[0].skill_name == "slack"
    assert skill_events[0].success is True
    assert skill_events[0].tenant_id == tenant_id


async def test_failed_tool_invocation_publishes_failure_event_and_502s(
    client, monkeypatch, fake_publisher
):
    headers, tenant_id, employee_id = auth_headers()
    agent = _agent(tenant_id=str(tenant_id), employee_id=str(employee_id), skills=["slack"])

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    async def fake_generate(**kwargs):
        return _tool_use_response()

    async def fake_invoke_skill(skill_id, *, tool_name, tool_input, bearer_token):
        raise SkillClientError(502, "Slack API error: channel_not_found")

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)
    monkeypatch.setattr(skill_client_module, "list_tools", _fake_list_tools)
    monkeypatch.setattr(runtime_module, "invoke_skill", fake_invoke_skill)

    resp = await client.post("/chat", json={"message": "post hi"}, headers=headers)
    assert resp.status_code == 502

    await fake_publisher.wait_for_publish()
    skill_events = [
        SkillUsageEvent.model_validate_json(payload)
        for routing_key, payload in fake_publisher.published
        if routing_key == ROUTING_KEY_SKILL_USAGE
    ]
    assert len(skill_events) == 1
    assert skill_events[0].success is False


async def test_agent_only_gets_tools_for_skills_in_its_allowlist(client, monkeypatch):
    """Skill Marketplace's /tools already filters to tenant-enabled +
    employee-connected; Agent Registry's `skills` allowlist is the last
    filter, applied here. An agent without "slack" in its own skills list
    never sees the tool, even if the tenant/employee both have it."""
    headers, tenant_id, employee_id = auth_headers()
    agent = _agent(
        tenant_id=str(tenant_id), employee_id=str(employee_id), skills=["google_calendar"]
    )

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    captured = {}

    async def fake_generate(**kwargs):
        captured.update(kwargs)
        return _llm_response()

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)
    monkeypatch.setattr(skill_client_module, "list_tools", _fake_list_tools)  # only offers "slack"

    resp = await client.post("/chat", json={"message": "hi"}, headers=headers)
    assert resp.status_code == 200
    assert captured["tools"] is None  # slack was offered, but not in this agent's allowlist


async def test_max_tool_iterations_forces_a_final_text_only_answer(client, monkeypatch):
    """A model that keeps calling tools forever must not leave the turn
    on a stale, possibly-empty tool-use response once
    MAX_TOOL_ITERATIONS is exhausted — one last call with tools=None
    forces a real text answer instead."""
    headers, tenant_id, employee_id = auth_headers()
    agent = _agent(tenant_id=str(tenant_id), employee_id=str(employee_id), skills=["slack"])

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    generate_calls = []

    async def fake_generate(**kwargs):
        generate_calls.append(kwargs)
        # Every single call before the forced final one keeps asking for
        # another tool call — a pathological/looping model.
        if len(generate_calls) <= runtime_module.MAX_TOOL_ITERATIONS:
            return _tool_use_response()
        return _llm_response(content="Here's a summary of everything I found.")

    async def fake_invoke_skill(skill_id, *, tool_name, tool_input, bearer_token):
        return {"ok": True}

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)
    monkeypatch.setattr(skill_client_module, "list_tools", _fake_list_tools)
    monkeypatch.setattr(runtime_module, "invoke_skill", fake_invoke_skill)

    resp = await client.post("/chat", json={"message": "post hi forever"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Here's a summary of everything I found."

    # MAX_TOOL_ITERATIONS tool-use rounds, plus exactly one forced final
    # call — not zero (the turn must still resolve) and not another
    # unbounded round (that call must not offer tools again).
    assert len(generate_calls) == runtime_module.MAX_TOOL_ITERATIONS + 1
    assert generate_calls[-1]["tools"] is None


async def test_system_prompt_lists_available_tools_and_instructs_proactive_use(
    client, monkeypatch
):
    headers, tenant_id, employee_id = auth_headers()
    agent = _agent(tenant_id=str(tenant_id), employee_id=str(employee_id), skills=["slack"])

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    captured = {}

    async def fake_generate(**kwargs):
        captured.update(kwargs)
        return _llm_response()

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)
    monkeypatch.setattr(skill_client_module, "list_tools", _fake_list_tools)

    resp = await client.post("/chat", json={"message": "hi"}, headers=headers)
    assert resp.status_code == 200

    system = captured["system"]
    # Names and describes the actual tool the agent has, by name — not
    # just relying on the provider's own function-calling metadata.
    assert "slack_post_message" in system
    assert "Post a message" in system
    # Instructs actually calling tools rather than narrating/describing
    # what it would do.
    assert "call the tool directly" in system.lower() or "call the" in system.lower()


async def test_system_prompt_omits_tools_section_when_agent_has_no_tools(client, monkeypatch):
    headers, tenant_id, employee_id = auth_headers()
    agent = _agent(tenant_id=str(tenant_id), employee_id=str(employee_id))  # skills=[]

    async def fake_get_agent(emp_id, *, bearer_token):
        return agent

    captured = {}

    async def fake_generate(**kwargs):
        captured.update(kwargs)
        return _llm_response()

    monkeypatch.setattr(runtime_module, "get_agent_for_employee", fake_get_agent)
    monkeypatch.setattr(runtime_module, "generate", fake_generate)
    monkeypatch.setattr(skill_client_module, "list_tools", _fake_list_tools)

    resp = await client.post("/chat", json={"message": "hi"}, headers=headers)
    assert resp.status_code == 200
    assert "slack_post_message" not in captured["system"]
