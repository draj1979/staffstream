import uuid

import httpx

from .config import settings


class LLMClientError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"LLM Gateway returned {status_code}: {detail}")


async def generate(
    *,
    bearer_token: str,
    model: str,
    system: str | None,
    messages: list[dict],
    temperature: float,
    agent_id: uuid.UUID | None = None,
) -> dict:
    async with httpx.AsyncClient(base_url=settings.llm_gateway_url, timeout=60.0) as client:
        resp = await client.post(
            "/generate",
            json={
                "model": model,
                "system": system,
                "messages": messages,
                "temperature": temperature,
                "agent_id": str(agent_id) if agent_id else None,
            },
            headers={"Authorization": bearer_token},
        )
    if resp.status_code >= 400:
        raise LLMClientError(resp.status_code, resp.text)
    return resp.json()
