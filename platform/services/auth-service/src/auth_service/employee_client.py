import uuid

import httpx

from auth import encode_system_token

from .config import settings


class EmployeeServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Employee Service returned {status_code}: {detail}")


async def create_employee(
    tenant_id: uuid.UUID,
    *,
    email: str,
    department: str | None,
    designation: str | None,
    phone: str | None,
    roles: list[str],
) -> dict:
    """Calls Employee Service's own /employees endpoint using a short-lived
    system-scoped token — auth-service doesn't touch Employee Service's
    database directly, it goes through the same API a real client would,
    just with elevated scope for this one bootstrap call."""
    system_token = encode_system_token(tenant_id)
    payload = {
        "email": email,
        "department": department,
        "designation": designation,
        "phone": phone,
        "roles": roles,
    }
    async with httpx.AsyncClient(base_url=settings.employee_service_url, timeout=10.0) as client:
        resp = await client.post(
            "/employees",
            json=payload,
            headers={"Authorization": f"Bearer {system_token}"},
        )
    if resp.status_code >= 400:
        raise EmployeeServiceError(resp.status_code, resp.text)
    return resp.json()
