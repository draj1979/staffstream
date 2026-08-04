import httpx

from .config import settings


class SkillClientError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Skill Marketplace returned {status_code}: {detail}")


async def list_tools(*, bearer_token: str) -> list[dict]:
    """Tools available to *this* employee right now — Skill Marketplace
    has already filtered to tenant-enabled + employee-connected; the
    agent's own `skills` allowlist is a further filter applied by
    skills.py, not here."""
    async with httpx.AsyncClient(base_url=settings.skill_marketplace_url, timeout=10.0) as client:
        resp = await client.get("/tools", headers={"Authorization": bearer_token})
    if resp.status_code >= 400:
        raise SkillClientError(resp.status_code, resp.text)
    return resp.json()


async def invoke_skill(
    skill_id: str, *, tool_name: str, tool_input: dict, bearer_token: str
) -> dict:
    async with httpx.AsyncClient(base_url=settings.skill_marketplace_url, timeout=30.0) as client:
        resp = await client.post(
            f"/skills/{skill_id}/invoke",
            json={"tool_name": tool_name, "input": tool_input},
            headers={"Authorization": bearer_token},
        )
    if resp.status_code >= 400:
        raise SkillClientError(resp.status_code, resp.text)
    return resp.json()["output"]
