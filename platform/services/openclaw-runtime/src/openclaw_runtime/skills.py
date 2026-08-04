"""Phase 8: real Skill Marketplace wiring — the "Load Skills" step from
CLAUDE.md's request flow. Skill Marketplace already filtered its /tools
response to skills the tenant has enabled *and* this employee has
personally connected; here we apply the last, agent-level filter — an
agent only gets a tool if the skill is in its own `skills` allowlist from
Agent Registry — and turn the result into Anthropic's tool-definition
shape, plus a name -> skill_id lookup so the tool-calling loop in
runtime.py knows which skill to invoke for each tool the LLM calls.
"""

from . import skill_client


async def load_tools(agent: dict, *, bearer_token: str) -> tuple[list[dict], dict[str, str]]:
    allowed_skills = set(agent.get("skills", []))
    if not allowed_skills:
        return [], {}

    available = await skill_client.list_tools(bearer_token=bearer_token)

    tools: list[dict] = []
    tool_to_skill: dict[str, str] = {}
    for tool in available:
        if tool["skill_id"] not in allowed_skills:
            continue
        tools.append(
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"],
            }
        )
        tool_to_skill[tool["name"]] = tool["skill_id"]

    return tools, tool_to_skill
