import uuid

from auth import decode_token

TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())


def headers(tenant_id: str) -> dict:
    return {"X-Tenant-Id": tenant_id}


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
