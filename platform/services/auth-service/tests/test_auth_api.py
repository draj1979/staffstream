import uuid

from auth import decode_token, encode_access_token

TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())


def headers(tenant_id: str) -> dict:
    return {"X-Tenant-Id": tenant_id}


def manager_headers(tenant_id: str, employee_id: uuid.UUID) -> dict:
    token = encode_access_token(uuid.UUID(tenant_id), employee_id, role="manager")
    return {"Authorization": f"Bearer {token}"}


async def test_signup_creates_employee_and_returns_tokens(client, fake_employee_service):
    resp = await client.post(
        "/auth/signup",
        json={"email": "ada@acme.com", "password": "correct horse battery staple"},
        headers=headers(TENANT_A),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tenant_id"] == TENANT_A
    assert "ada@acme.com" in fake_employee_service

    claims = decode_token(body["access_token"])
    assert claims["tenant_id"] == TENANT_A
    assert claims["sub"] == body["employee_id"]
    assert claims["scope"] == "user"


async def test_signup_rejects_duplicate_email_in_same_tenant(client, fake_employee_service):
    payload = {"email": "dup@acme.com", "password": "correct horse battery staple"}
    resp = await client.post("/auth/signup", json=payload, headers=headers(TENANT_A))
    assert resp.status_code == 201

    resp = await client.post("/auth/signup", json=payload, headers=headers(TENANT_A))
    assert resp.status_code == 409


async def test_same_email_allowed_in_different_tenants(client, fake_employee_service):
    payload = {"email": "shared@acme.com", "password": "correct horse battery staple"}
    resp = await client.post("/auth/signup", json=payload, headers=headers(TENANT_A))
    assert resp.status_code == 201
    resp = await client.post("/auth/signup", json=payload, headers=headers(TENANT_B))
    assert resp.status_code == 201


async def test_login_with_correct_password_succeeds(client, fake_employee_service):
    payload = {"email": "bob@acme.com", "password": "hunter2hunter2"}
    await client.post("/auth/signup", json=payload, headers=headers(TENANT_A))

    resp = await client.post(
        "/auth/login",
        json={"email": "bob@acme.com", "password": "hunter2hunter2"},
        headers=headers(TENANT_A),
    )
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == TENANT_A


async def test_login_with_wrong_password_is_401(client, fake_employee_service):
    payload = {"email": "carol@acme.com", "password": "correct-password-123"}
    await client.post("/auth/signup", json=payload, headers=headers(TENANT_A))

    resp = await client.post(
        "/auth/login",
        json={"email": "carol@acme.com", "password": "wrong-password"},
        headers=headers(TENANT_A),
    )
    assert resp.status_code == 401


async def test_login_unknown_email_is_401(client, fake_employee_service):
    resp = await client.post(
        "/auth/login",
        json={"email": "nobody@acme.com", "password": "whatever123"},
        headers=headers(TENANT_A),
    )
    assert resp.status_code == 401


async def test_login_requires_correct_tenant_header(client, fake_employee_service):
    payload = {"email": "dana@acme.com", "password": "correct-password-123"}
    await client.post("/auth/signup", json=payload, headers=headers(TENANT_A))

    # Same email exists, but under a different tenant context — not found there.
    resp = await client.post(
        "/auth/login",
        json={"email": "dana@acme.com", "password": "correct-password-123"},
        headers=headers(TENANT_B),
    )
    assert resp.status_code == 401


async def test_refresh_rotates_token_and_old_one_stops_working(client, fake_employee_service):
    payload = {"email": "erin@acme.com", "password": "correct-password-123"}
    signup_resp = await client.post("/auth/signup", json=payload, headers=headers(TENANT_A))
    old_refresh_token = signup_resp.json()["refresh_token"]

    resp = await client.post(
        "/auth/refresh",
        json={"refresh_token": old_refresh_token},
        headers=headers(TENANT_A),
    )
    assert resp.status_code == 200
    new_refresh_token = resp.json()["refresh_token"]
    assert new_refresh_token != old_refresh_token

    # Old refresh token was rotated out — replay fails.
    resp = await client.post(
        "/auth/refresh",
        json={"refresh_token": old_refresh_token},
        headers=headers(TENANT_A),
    )
    assert resp.status_code == 401

    # New one still works.
    resp = await client.post(
        "/auth/refresh",
        json={"refresh_token": new_refresh_token},
        headers=headers(TENANT_A),
    )
    assert resp.status_code == 200


async def test_refresh_with_garbage_token_is_401(client, fake_employee_service):
    resp = await client.post(
        "/auth/refresh", json={"refresh_token": "not-a-real-token"}, headers=headers(TENANT_A)
    )
    assert resp.status_code == 401


async def test_logout_revokes_refresh_token(client, fake_employee_service):
    payload = {"email": "frank@acme.com", "password": "correct-password-123"}
    signup_resp = await client.post("/auth/signup", json=payload, headers=headers(TENANT_A))
    refresh_token = signup_resp.json()["refresh_token"]

    resp = await client.post(
        "/auth/logout", json={"refresh_token": refresh_token}, headers=headers(TENANT_A)
    )
    assert resp.status_code == 204

    resp = await client.post(
        "/auth/refresh", json={"refresh_token": refresh_token}, headers=headers(TENANT_A)
    )
    assert resp.status_code == 401


async def test_logout_is_idempotent_for_unknown_token(client, fake_employee_service):
    resp = await client.post(
        "/auth/logout", json={"refresh_token": "never-issued"}, headers=headers(TENANT_A)
    )
    assert resp.status_code == 204


async def _create_credentialless_employee(fake_employee_service, tenant_id: str, email: str) -> str:
    """Mirrors what POST /employees on Employee Service leaves behind: a
    record with no row in auth-service's credentials table at all."""
    employee_id = str(uuid.uuid4())
    fake_employee_service[email] = {
        "employee_id": employee_id,
        "tenant_id": tenant_id,
        "email": email,
        "department": None,
        "designation": None,
        "phone": None,
        "roles": [],
    }
    return employee_id


async def test_invite_then_accept_issues_working_credentials(client, fake_employee_service):
    manager_id = await _create_credentialless_employee(fake_employee_service, TENANT_A, "mgr@acme.com")
    employee_id = await _create_credentialless_employee(
        fake_employee_service, TENANT_A, "newhire@acme.com"
    )

    resp = await client.post(
        f"/auth/invite/{employee_id}", headers=manager_headers(TENANT_A, uuid.UUID(manager_id))
    )
    assert resp.status_code == 200
    invite_token = resp.json()["invite_token"]

    resp = await client.post(
        "/auth/invite/accept", json={"token": invite_token, "password": "a-real-password-123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["employee_id"] == employee_id
    assert body["tenant_id"] == TENANT_A

    # The new credential actually works for a normal login afterwards.
    resp = await client.post(
        "/auth/login",
        json={"email": "newhire@acme.com", "password": "a-real-password-123"},
        headers=headers(TENANT_A),
    )
    assert resp.status_code == 200


async def test_invite_rejects_employee_with_existing_credentials(client, fake_employee_service):
    manager_id = await _create_credentialless_employee(fake_employee_service, TENANT_A, "mgr2@acme.com")
    signup_resp = await client.post(
        "/auth/signup",
        json={"email": "already-has-creds@acme.com", "password": "correct-password-123"},
        headers=headers(TENANT_A),
    )
    employee_id = signup_resp.json()["employee_id"]

    resp = await client.post(
        f"/auth/invite/{employee_id}", headers=manager_headers(TENANT_A, uuid.UUID(manager_id))
    )
    assert resp.status_code == 409


async def test_invite_accept_rejects_reuse(client, fake_employee_service):
    manager_id = await _create_credentialless_employee(fake_employee_service, TENANT_A, "mgr3@acme.com")
    employee_id = await _create_credentialless_employee(
        fake_employee_service, TENANT_A, "onceonly@acme.com"
    )
    resp = await client.post(
        f"/auth/invite/{employee_id}", headers=manager_headers(TENANT_A, uuid.UUID(manager_id))
    )
    invite_token = resp.json()["invite_token"]

    resp = await client.post(
        "/auth/invite/accept", json={"token": invite_token, "password": "first-password-123"}
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/auth/invite/accept", json={"token": invite_token, "password": "second-password-123"}
    )
    assert resp.status_code == 409


async def test_invite_accept_rejects_garbage_token(client, fake_employee_service):
    resp = await client.post(
        "/auth/invite/accept", json={"token": "not-a-real-token", "password": "whatever-123"}
    )
    assert resp.status_code == 400


async def test_invite_unknown_employee_is_404(client, fake_employee_service):
    manager_id = await _create_credentialless_employee(fake_employee_service, TENANT_A, "mgr4@acme.com")
    resp = await client.post(
        f"/auth/invite/{uuid.uuid4()}", headers=manager_headers(TENANT_A, uuid.UUID(manager_id))
    )
    assert resp.status_code == 404


async def test_invite_requires_manager_role(client, fake_employee_service):
    employee_id = await _create_credentialless_employee(
        fake_employee_service, TENANT_A, "plain@acme.com"
    )
    plain_employee_token = encode_access_token(
        uuid.UUID(TENANT_A), uuid.uuid4(), role="employee"
    )
    resp = await client.post(
        f"/auth/invite/{employee_id}",
        headers={"Authorization": f"Bearer {plain_employee_token}"},
    )
    assert resp.status_code == 403
