import uuid

import httpx

from .config import settings


class EmployeeClientError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Employee Service returned {status_code}: {detail}")


async def get_employee(employee_id: uuid.UUID, *, bearer_token: str) -> dict:
    """Fetched fresh every call, same as the agent — OpenClaw has no cache
    of its own. Used only to read the employee's department for Knowledge
    Platform's department-scoped retrieval."""
    async with httpx.AsyncClient(base_url=settings.employee_service_url, timeout=10.0) as client:
        resp = await client.get(
            f"/employees/{employee_id}", headers={"Authorization": bearer_token}
        )
    if resp.status_code >= 400:
        raise EmployeeClientError(resp.status_code, resp.text)
    return resp.json()
