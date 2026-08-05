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


async def get_employee(tenant_id: uuid.UUID, employee_id: uuid.UUID) -> dict | None:
    """Used to look up an employee's current `roles` at login/refresh
    time, so the minted JWT always reflects whatever Employee Service has
    on file right now — never cached, same "always fetch fresh" pattern
    every other cross-service call in this platform follows."""
    system_token = encode_system_token(tenant_id)
    async with httpx.AsyncClient(base_url=settings.employee_service_url, timeout=10.0) as client:
        resp = await client.get(
            f"/employees/{employee_id}", headers={"Authorization": f"Bearer {system_token}"}
        )
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise EmployeeServiceError(resp.status_code, resp.text)
    return resp.json()


async def get_employee_by_email(tenant_id: uuid.UUID, email: str) -> dict | None:
    """Used by the SSO callback to map a verified id_token email back to
    the existing employee_id/tenant_id model — SSO never creates a
    parallel identity, it just authenticates an employee that already
    exists (see routers/sso.py's callback for the "no match" case)."""
    system_token = encode_system_token(tenant_id)
    async with httpx.AsyncClient(base_url=settings.employee_service_url, timeout=10.0) as client:
        resp = await client.get(
            f"/employees/by-email/{email}", headers={"Authorization": f"Bearer {system_token}"}
        )
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise EmployeeServiceError(resp.status_code, resp.text)
    return resp.json()
