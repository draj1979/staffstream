import uuid

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from auth import (
    Principal,
    encode_access_token,
    encode_system_token,
    require_auth,
    require_role,
)
from tenancy import try_get_current_tenant_id


def build_app():
    app = FastAPI()

    @app.get("/user-only")
    async def user_only(principal: Principal = Depends(require_auth())):
        return {
            "tenant_id": str(principal.tenant_id),
            "employee_id": str(principal.employee_id),
            "context_tenant_id": str(try_get_current_tenant_id()),
        }

    @app.get("/user-or-system")
    async def user_or_system(
        principal: Principal = Depends(require_auth(allowed_scopes=("user", "system"))),
    ):
        return {"scope": principal.scope}

    @app.get("/admin-only")
    async def admin_only(principal: Principal = Depends(require_role("admin"))):
        return {"role": principal.role}

    @app.get("/manager-or-above")
    async def manager_or_above(principal: Principal = Depends(require_role("manager"))):
        return {"role": principal.role}

    return app


async def _client():
    transport = ASGITransport(app=build_app())
    return AsyncClient(transport=transport, base_url="http://test")


async def test_missing_authorization_header_is_401():
    async with await _client() as client:
        resp = await client.get("/user-only")
    assert resp.status_code == 401


async def test_valid_user_token_sets_tenant_context_and_returns_principal():
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    token = encode_access_token(tenant_id, employee_id)

    async with await _client() as client:
        resp = await client.get("/user-only", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == str(tenant_id)
    assert body["employee_id"] == str(employee_id)
    assert body["context_tenant_id"] == str(tenant_id)


async def test_system_token_rejected_on_user_only_route():
    token = encode_system_token(uuid.uuid4())
    async with await _client() as client:
        resp = await client.get("/user-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_system_token_accepted_on_dual_scope_route():
    token = encode_system_token(uuid.uuid4())
    async with await _client() as client:
        resp = await client.get("/user-or-system", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["scope"] == "system"


async def test_garbage_token_is_401():
    async with await _client() as client:
        resp = await client.get("/user-only", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


async def test_access_token_defaults_to_employee_role():
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    token = encode_access_token(tenant_id, employee_id)

    async with await _client() as client:
        resp = await client.get("/manager-or-above", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403  # default "employee" role doesn't satisfy "manager"


async def test_access_token_carries_explicit_role():
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    token = encode_access_token(tenant_id, employee_id, role="admin")

    async with await _client() as client:
        resp = await client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


async def test_require_role_allows_higher_ranked_role():
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    token = encode_access_token(tenant_id, employee_id, role="admin")

    async with await _client() as client:
        resp = await client.get(
            "/manager-or-above", headers={"Authorization": f"Bearer {token}"}
        )
    assert resp.status_code == 200


async def test_require_role_rejects_system_scoped_token():
    token = encode_system_token(uuid.uuid4())
    async with await _client() as client:
        resp = await client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
