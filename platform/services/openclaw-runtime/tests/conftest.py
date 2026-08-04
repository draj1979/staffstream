import pytest
from httpx import ASGITransport, AsyncClient
from openclaw_runtime import employee_client, knowledge_client, memory_client
from openclaw_runtime.main import app


@pytest.fixture(autouse=True)
def stub_memory_service(monkeypatch):
    """Stubs the HTTP calls to Memory Service so chat tests don't need a
    real one running. Defaults to empty memory (fresh employee, nothing
    learned yet) — tests that care about specific memory content override
    these via monkeypatch themselves."""
    appended = []

    async def fake_get_conversation_history(memory_namespace, *, bearer_token, limit=20):
        return []

    async def fake_get_long_term_memory(memory_namespace, *, bearer_token, limit=10):
        return []

    async def fake_get_preferences(memory_namespace, *, bearer_token):
        return []

    async def fake_get_learned_facts(memory_namespace, *, bearer_token, limit=10):
        return []

    async def fake_append_conversation_turn(memory_namespace, *, bearer_token, role, content):
        entry = {"memory_namespace": memory_namespace, "role": role, "content": content}
        appended.append(entry)
        return entry

    monkeypatch.setattr(memory_client, "get_conversation_history", fake_get_conversation_history)
    monkeypatch.setattr(memory_client, "get_long_term_memory", fake_get_long_term_memory)
    monkeypatch.setattr(memory_client, "get_preferences", fake_get_preferences)
    monkeypatch.setattr(memory_client, "get_learned_facts", fake_get_learned_facts)
    monkeypatch.setattr(memory_client, "append_conversation_turn", fake_append_conversation_turn)
    return appended


@pytest.fixture(autouse=True)
def stub_knowledge_platform(monkeypatch):
    """Stubs Employee Service (for department lookup) and Knowledge
    Service (for retrieval) so chat tests don't need either running.
    Defaults: no department, no matching knowledge — tests that care
    override these via monkeypatch themselves."""

    async def fake_get_employee(employee_id, *, bearer_token):
        return {"employee_id": str(employee_id), "department": None}

    async def fake_search_knowledge(*, bearer_token, query, department, employee_id, top_k=5):
        return []

    monkeypatch.setattr(employee_client, "get_employee", fake_get_employee)
    monkeypatch.setattr(knowledge_client, "search_knowledge", fake_search_knowledge)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
