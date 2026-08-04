import uuid

import httpx

from .config import settings


class KnowledgeClientError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Knowledge Service returned {status_code}: {detail}")


async def search_knowledge(
    *,
    bearer_token: str,
    query: str,
    department: str | None,
    employee_id: uuid.UUID | None,
    top_k: int = 5,
) -> list[dict]:
    async with httpx.AsyncClient(base_url=settings.knowledge_service_url, timeout=15.0) as client:
        resp = await client.post(
            "/search",
            json={
                "query": query,
                "department": department,
                "employee_id": str(employee_id) if employee_id else None,
                "top_k": top_k,
            },
            headers={"Authorization": bearer_token},
        )
    if resp.status_code >= 400:
        raise KnowledgeClientError(resp.status_code, resp.text)
    return resp.json()
