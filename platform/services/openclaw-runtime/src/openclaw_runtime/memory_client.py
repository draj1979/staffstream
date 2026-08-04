import httpx

from .config import settings


class MemoryClientError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Memory Service returned {status_code}: {detail}")


def _client(bearer_token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.memory_service_url,
        timeout=10.0,
        headers={"Authorization": bearer_token},
    )


async def _get(path: str, *, bearer_token: str, params: dict | None = None) -> list | dict:
    async with _client(bearer_token) as client:
        resp = await client.get(path, params=params)
    if resp.status_code >= 400:
        raise MemoryClientError(resp.status_code, resp.text)
    return resp.json()


async def get_conversation_history(
    memory_namespace: str, *, bearer_token: str, limit: int = 20
) -> list[dict]:
    return await _get(
        f"/memory/{memory_namespace}/conversation",
        bearer_token=bearer_token,
        params={"limit": limit},
    )


async def get_long_term_memory(
    memory_namespace: str, *, bearer_token: str, limit: int = 10
) -> list[dict]:
    return await _get(
        f"/memory/{memory_namespace}/long-term", bearer_token=bearer_token, params={"limit": limit}
    )


async def get_preferences(memory_namespace: str, *, bearer_token: str) -> list[dict]:
    return await _get(f"/memory/{memory_namespace}/preferences", bearer_token=bearer_token)


async def get_learned_facts(
    memory_namespace: str, *, bearer_token: str, limit: int = 10
) -> list[dict]:
    return await _get(
        f"/memory/{memory_namespace}/facts", bearer_token=bearer_token, params={"limit": limit}
    )


async def append_conversation_turn(
    memory_namespace: str, *, bearer_token: str, role: str, content: str
) -> dict:
    async with _client(bearer_token) as client:
        resp = await client.post(
            f"/memory/{memory_namespace}/conversation", json={"role": role, "content": content}
        )
    if resp.status_code >= 400:
        raise MemoryClientError(resp.status_code, resp.text)
    return resp.json()
