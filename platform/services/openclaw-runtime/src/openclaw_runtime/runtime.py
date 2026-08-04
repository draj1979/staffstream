import uuid

from auth import Principal

from . import knowledge, memory
from .agent_client import get_agent_for_employee
from .llm_client import generate
from .schemas import ChatResponse


async def run_chat_turn(principal: Principal, message: str, *, bearer_token: str) -> ChatResponse:
    """The OpenClaw Runtime entry point for a single chat turn.

    Deliberately stateless: agent config, conversation history, and
    knowledge are all re-fetched from their owning services on every call —
    nothing is cached in this process between requests. A change to an
    agent's model or prompt takes effect on the very next message, with no
    restart or cache invalidation anywhere.
    """
    agent = await get_agent_for_employee(principal.employee_id, bearer_token=bearer_token)

    history = await memory.load_conversation_history(principal.tenant_id, principal.employee_id)
    knowledge_context = await knowledge.load_knowledge_context(
        principal.tenant_id, principal.employee_id, agent
    )

    system_prompt = agent["prompt"]
    if agent.get("personality"):
        system_prompt = f"{system_prompt}\n\nPersonality: {agent['personality']}"
    if knowledge_context:
        system_prompt = f"{system_prompt}\n\nRelevant knowledge:\n{knowledge_context}"

    messages = [*history, {"role": "user", "content": message}]

    llm_response = await generate(
        bearer_token=bearer_token,
        model=agent["model"],
        system=system_prompt,
        messages=messages,
        temperature=agent["temperature"],
    )

    await memory.store_turn(
        principal.tenant_id,
        principal.employee_id,
        user_message=message,
        assistant_reply=llm_response["content"],
    )

    return ChatResponse(
        reply=llm_response["content"],
        agent_id=uuid.UUID(agent["agent_id"]),
        model=llm_response["model"],
        usage=llm_response["usage"],
    )
