import uuid

from auth import Principal

from . import knowledge, memory
from .agent_client import get_agent_for_employee
from .llm_client import generate
from .schemas import ChatResponse


def _build_system_prompt(agent: dict, memory_context: dict, knowledge_context: str | None) -> str:
    parts = [agent["prompt"]]

    if agent.get("personality"):
        parts.append(f"Personality: {agent['personality']}")

    if memory_context["preferences"]:
        prefs = ", ".join(f"{p['key']}={p['value']}" for p in memory_context["preferences"])
        parts.append(f"Known preferences: {prefs}")

    if memory_context["long_term"]:
        notes = "\n".join(f"- {entry['content']}" for entry in memory_context["long_term"])
        parts.append(f"Long-term memory:\n{notes}")

    if memory_context["facts"]:
        facts = "\n".join(f"- {fact['content']}" for fact in memory_context["facts"])
        parts.append(f"Things learned about this employee:\n{facts}")

    if knowledge_context:
        parts.append(f"Relevant knowledge:\n{knowledge_context}")

    return "\n\n".join(parts)


async def run_chat_turn(principal: Principal, message: str, *, bearer_token: str) -> ChatResponse:
    """The OpenClaw Runtime entry point for a single chat turn.

    Deliberately stateless: agent config, memory, and knowledge are all
    re-fetched from their owning services on every call — nothing is
    cached in this process between requests. A change to an agent's model,
    prompt, or memory takes effect on the very next message, with no
    restart or cache invalidation anywhere.
    """
    agent = await get_agent_for_employee(principal.employee_id, bearer_token=bearer_token)
    memory_namespace = agent["memory_namespace"]

    memory_context = await memory.load_context(memory_namespace, bearer_token=bearer_token)
    knowledge_context = await knowledge.load_knowledge_context(
        principal.tenant_id, principal.employee_id, agent
    )

    system_prompt = _build_system_prompt(agent, memory_context, knowledge_context)
    history = [
        {"role": turn["role"], "content": turn["content"]} for turn in memory_context["history"]
    ]
    messages = [*history, {"role": "user", "content": message}]

    llm_response = await generate(
        bearer_token=bearer_token,
        model=agent["model"],
        system=system_prompt,
        messages=messages,
        temperature=agent["temperature"],
    )

    await memory.store_turn(
        memory_namespace,
        bearer_token=bearer_token,
        user_message=message,
        assistant_reply=llm_response["content"],
    )

    return ChatResponse(
        reply=llm_response["content"],
        agent_id=uuid.UUID(agent["agent_id"]),
        model=llm_response["model"],
        usage=llm_response["usage"],
    )
