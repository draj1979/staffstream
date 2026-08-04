import json
import uuid
from dataclasses import dataclass, field

from auth import Principal

from . import knowledge, memory, skills
from .agent_client import get_agent_for_employee
from .llm_client import generate
from .schemas import ChatResponse, Usage
from .skill_client import SkillClientError, invoke_skill

# Bounds the LLM <-> tool round trips within a single /chat call. A well-
# behaved model converges in 1-3 tool calls; this is a safety valve
# against a model that keeps calling tools forever, not a normal path.
MAX_TOOL_ITERATIONS = 5


@dataclass
class TurnContext:
    """Populated progressively as run_chat_turn proceeds, so the caller
    (chat.py) can still report which agent was involved — and which
    skills were used, even on a later failure — even if a later step
    fails. agent_id is set right after the agent fetch succeeds, before
    memory/knowledge/LLM ever run; skill_usages grows one entry per tool
    call as the tool-calling loop executes them."""

    agent_id: uuid.UUID | None = None
    skill_usages: list[dict] = field(default_factory=list)


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


async def _run_tool_calling_loop(
    *,
    agent: dict,
    system_prompt: str,
    messages: list[dict],
    tool_to_skill: dict[str, str],
    tools: list[dict],
    bearer_token: str,
    context: TurnContext,
) -> dict:
    """Load Skills -> LLM -> Tool Calls -> (repeat) -> Generate Response,
    per CLAUDE.md's request flow. Returns the final LLM response dict
    (the one whose stop_reason isn't "tool_use", or whichever response is
    on hand once MAX_TOOL_ITERATIONS is reached).
    """
    total_input_tokens = 0
    total_output_tokens = 0
    response: dict | None = None

    for _ in range(MAX_TOOL_ITERATIONS):
        response = await generate(
            bearer_token=bearer_token,
            model=agent["model"],
            system=system_prompt,
            messages=messages,
            temperature=agent["temperature"],
            agent_id=context.agent_id,
            tools=tools or None,
        )
        total_input_tokens += response["usage"]["input_tokens"]
        total_output_tokens += response["usage"]["output_tokens"]

        tool_calls = response.get("tool_calls") or []
        if not tool_calls:
            break

        assistant_blocks = []
        if response["content"]:
            assistant_blocks.append({"type": "text", "text": response["content"]})
        assistant_blocks.extend(
            {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["input"]}
            for tc in tool_calls
        )
        messages.append({"role": "assistant", "content": assistant_blocks})

        result_blocks = []
        for tc in tool_calls:
            skill_id = tool_to_skill.get(tc["name"])
            success = False
            try:
                if skill_id is None:
                    raise SkillClientError(500, f"Unknown tool {tc['name']!r}")
                output = await invoke_skill(
                    skill_id,
                    tool_name=tc["name"],
                    tool_input=tc["input"],
                    bearer_token=bearer_token,
                )
                success = True
                result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tc["id"],
                        "content": json.dumps(output),
                    }
                )
            finally:
                context.skill_usages.append(
                    {"skill_name": skill_id or tc["name"], "success": success}
                )
        messages.append({"role": "user", "content": result_blocks})

    response["usage"] = {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
    }
    return response


async def run_chat_turn(
    principal: Principal,
    message: str,
    *,
    bearer_token: str,
    context: TurnContext | None = None,
) -> ChatResponse:
    """The OpenClaw Runtime entry point for a single chat turn.

    Deliberately stateless: agent config, memory, knowledge, and available
    skills are all re-fetched from their owning services on every call —
    nothing is cached in this process between requests. A change to an
    agent's model, prompt, memory, or connected skills takes effect on
    the very next message, with no restart or cache invalidation anywhere.
    """
    if context is None:
        context = TurnContext()

    agent = await get_agent_for_employee(principal.employee_id, bearer_token=bearer_token)
    context.agent_id = uuid.UUID(agent["agent_id"])
    memory_namespace = agent["memory_namespace"]

    memory_context = await memory.load_context(memory_namespace, bearer_token=bearer_token)
    knowledge_context = await knowledge.load_knowledge_context(
        principal.tenant_id, principal.employee_id, agent, bearer_token=bearer_token, query=message
    )
    tools, tool_to_skill = await skills.load_tools(agent, bearer_token=bearer_token)

    system_prompt = _build_system_prompt(agent, memory_context, knowledge_context)
    history = [
        {"role": turn["role"], "content": turn["content"]} for turn in memory_context["history"]
    ]
    messages = [*history, {"role": "user", "content": message}]

    llm_response = await _run_tool_calling_loop(
        agent=agent,
        system_prompt=system_prompt,
        messages=messages,
        tool_to_skill=tool_to_skill,
        tools=tools,
        bearer_token=bearer_token,
        context=context,
    )

    await memory.store_turn(
        memory_namespace,
        bearer_token=bearer_token,
        user_message=message,
        assistant_reply=llm_response["content"],
    )

    return ChatResponse(
        reply=llm_response["content"],
        agent_id=context.agent_id,
        model=llm_response["model"],
        usage=Usage(**llm_response["usage"]),
    )
