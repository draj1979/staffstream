import json
import time
import uuid

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from auth import decode_token, encode_access_token, encode_state_token
from events import ROUTING_KEY_AUDIT, AuditEvent

TENANT = uuid.uuid4()

GOOGLE_DISCOVERY = {
    "issuer": "https://accounts.google.com",
    "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_endpoint": "https://oauth2.googleapis.com/token",
    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
}


def admin_headers(tenant_id: uuid.UUID = TENANT) -> dict:
    token = encode_access_token(tenant_id, uuid.uuid4(), role="admin")
    return {"Authorization": f"Bearer {token}"}


def employee_headers(tenant_id: uuid.UUID = TENANT) -> dict:
    token = encode_access_token(tenant_id, uuid.uuid4(), role="employee")
    return {"Authorization": f"Bearer {token}"}


def _keypair_and_jwks(kid: str = "k1"):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = kid
    return private_key, {"keys": [jwk]}


def _sign(private_key, *, kid, issuer, audience, email, extra=None):
    now = int(time.time())
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": str(uuid.uuid4()),
        "email": email,
        "iat": now,
        "exp": now + 300,
    }
    claims.update(extra or {})
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def _google_discovery_handler(id_token: str | None = None, jwks: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "openid-configuration" in url:
            return httpx.Response(200, json=GOOGLE_DISCOVERY)
        if url == GOOGLE_DISCOVERY["token_endpoint"]:
            return httpx.Response(200, json={"id_token": id_token, "access_token": "x"})
        if url == GOOGLE_DISCOVERY["jwks_uri"]:
            return httpx.Response(200, json=jwks)
        raise AssertionError(f"unexpected call to {url}")

    return handler


async def test_set_sso_config_requires_admin(client):
    resp = await client.put(
        "/auth/sso/config/google_workspace",
        json={"client_id": "c", "client_secret": "s"},
        headers=employee_headers(),
    )
    assert resp.status_code == 403


async def test_set_sso_config_unknown_provider_is_404(client):
    resp = await client.put(
        "/auth/sso/config/okta",
        json={"client_id": "c", "client_secret": "s"},
        headers=admin_headers(),
    )
    assert resp.status_code == 404


async def test_auth0_requires_issuer_domain(client):
    resp = await client.put(
        "/auth/sso/config/auth0",
        json={"client_id": "c", "client_secret": "s"},
        headers=admin_headers(),
    )
    assert resp.status_code == 400


async def test_set_and_list_sso_config_never_returns_secret(client):
    resp = await client.put(
        "/auth/sso/config/google_workspace",
        json={
            "client_id": "client-123",
            "client_secret": "super-secret",
            "hosted_domain": "acme.com",
        },
        headers=admin_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "client_secret" not in body
    assert body["client_id"] == "client-123"
    assert body["hosted_domain"] == "acme.com"

    resp = await client.get("/auth/sso/config", headers=admin_headers())
    assert resp.status_code == 200
    assert all("client_secret" not in row for row in resp.json())


async def test_sso_config_publishes_audit_event(client, fake_publisher):
    resp = await client.put(
        "/auth/sso/config/google_workspace",
        json={"client_id": "client-123", "client_secret": "s"},
        headers=admin_headers(),
    )
    assert resp.status_code == 200

    await fake_publisher.wait_for_publish()
    routing_key, payload = fake_publisher.published[0]
    assert routing_key == ROUTING_KEY_AUDIT
    event = AuditEvent.model_validate_json(payload)
    assert event.action == "sso.config_changed"
    assert event.target_id == "google_workspace"


async def test_login_redirects_to_provider_when_enabled(client, http_handler):
    tenant_id = uuid.uuid4()
    await client.put(
        "/auth/sso/config/google_workspace",
        json={"client_id": "client-123", "client_secret": "s"},
        headers=admin_headers(tenant_id),
    )
    http_handler.handler = _google_discovery_handler()

    resp = await client.get(
        f"/auth/sso/login/{tenant_id}/google_workspace", follow_redirects=False
    )
    assert resp.status_code == 307
    assert resp.headers["location"].startswith(GOOGLE_DISCOVERY["authorization_endpoint"])
    assert "state=" in resp.headers["location"]


async def test_login_404_when_not_configured(client):
    resp = await client.get(f"/auth/sso/login/{uuid.uuid4()}/google_workspace")
    assert resp.status_code == 404


async def test_login_404_when_configured_but_disabled(client):
    tenant_id = uuid.uuid4()
    await client.put(
        "/auth/sso/config/google_workspace",
        json={"client_id": "client-123", "client_secret": "s", "enabled": False},
        headers=admin_headers(tenant_id),
    )
    resp = await client.get(f"/auth/sso/login/{tenant_id}/google_workspace")
    assert resp.status_code == 404


async def test_callback_rejects_forged_state(client):
    resp = await client.get(
        "/auth/sso/callback/google_workspace", params={"code": "c", "state": "not-a-real-token"}
    )
    assert resp.status_code == 400


async def test_callback_surfaces_provider_error(client):
    resp = await client.get(
        "/auth/sso/callback/google_workspace", params={"error": "access_denied"}
    )
    assert resp.status_code == 400


async def test_full_callback_flow_issues_tokens_for_existing_employee(
    client, http_handler, fake_employee_service
):
    tenant_id = uuid.uuid4()
    await client.put(
        "/auth/sso/config/google_workspace",
        json={"client_id": "client-123", "client_secret": "s", "hosted_domain": "acme.com"},
        headers=admin_headers(tenant_id),
    )

    # Pre-existing employee — SSO maps to this, never creates a new one.
    existing = {
        "employee_id": str(uuid.uuid4()),
        "tenant_id": str(tenant_id),
        "email": "ada@acme.com",
        "department": "Engineering",
        "designation": None,
        "phone": None,
        "roles": ["manager"],
    }
    fake_employee_service["ada@acme.com"] = existing

    private_key, jwks = _keypair_and_jwks()
    id_token = _sign(
        private_key,
        kid="k1",
        issuer=GOOGLE_DISCOVERY["issuer"],
        audience="client-123",
        email="ada@acme.com",
        extra={"hd": "acme.com"},
    )
    http_handler.handler = _google_discovery_handler(id_token=id_token, jwks=jwks)

    state = encode_state_token({"tenant_id": str(tenant_id), "provider": "google_workspace"})
    resp = await client.get(
        "/auth/sso/callback/google_workspace", params={"code": "authcode", "state": state}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["employee_id"] == existing["employee_id"]
    assert body["tenant_id"] == str(tenant_id)

    claims = decode_token(body["access_token"])
    assert claims["role"] == "manager"
    assert claims["sub"] == existing["employee_id"]


async def test_callback_rejects_wrong_hosted_domain(client, http_handler, fake_employee_service):
    tenant_id = uuid.uuid4()
    await client.put(
        "/auth/sso/config/google_workspace",
        json={"client_id": "client-123", "client_secret": "s", "hosted_domain": "acme.com"},
        headers=admin_headers(tenant_id),
    )
    fake_employee_service["ada@notacme.com"] = {
        "employee_id": str(uuid.uuid4()),
        "tenant_id": str(tenant_id),
        "email": "ada@notacme.com",
        "department": None,
        "designation": None,
        "phone": None,
        "roles": [],
    }

    private_key, jwks = _keypair_and_jwks()
    id_token = _sign(
        private_key,
        kid="k1",
        issuer=GOOGLE_DISCOVERY["issuer"],
        audience="client-123",
        email="ada@notacme.com",
        extra={"hd": "someone-elses-domain.com"},
    )
    http_handler.handler = _google_discovery_handler(id_token=id_token, jwks=jwks)

    state = encode_state_token({"tenant_id": str(tenant_id), "provider": "google_workspace"})
    resp = await client.get(
        "/auth/sso/callback/google_workspace", params={"code": "authcode", "state": state}
    )
    assert resp.status_code == 403


async def test_callback_no_matching_employee_is_404(client, http_handler, fake_employee_service):
    tenant_id = uuid.uuid4()
    await client.put(
        "/auth/sso/config/google_workspace",
        json={"client_id": "client-123", "client_secret": "s"},
        headers=admin_headers(tenant_id),
    )

    private_key, jwks = _keypair_and_jwks()
    id_token = _sign(
        private_key,
        kid="k1",
        issuer=GOOGLE_DISCOVERY["issuer"],
        audience="client-123",
        email="nobody@acme.com",
    )
    http_handler.handler = _google_discovery_handler(id_token=id_token, jwks=jwks)

    state = encode_state_token({"tenant_id": str(tenant_id), "provider": "google_workspace"})
    resp = await client.get(
        "/auth/sso/callback/google_workspace", params={"code": "authcode", "state": state}
    )
    assert resp.status_code == 404


async def test_callback_rejects_tampered_id_token_signature(
    client, http_handler, fake_employee_service
):
    """The exchange returns a syntactically valid id_token, but it wasn't
    signed by any key in the tenant's JWKS — proves signature
    verification is real, not just claim-shape checking."""
    tenant_id = uuid.uuid4()
    await client.put(
        "/auth/sso/config/google_workspace",
        json={"client_id": "client-123", "client_secret": "s"},
        headers=admin_headers(tenant_id),
    )
    fake_employee_service["ada@acme.com"] = {
        "employee_id": str(uuid.uuid4()),
        "tenant_id": str(tenant_id),
        "email": "ada@acme.com",
        "department": None,
        "designation": None,
        "phone": None,
        "roles": [],
    }

    _, real_jwks = _keypair_and_jwks(kid="k1")
    forged_key, _ = _keypair_and_jwks(kid="k1")  # different keypair, same kid
    id_token = _sign(
        forged_key,
        kid="k1",
        issuer=GOOGLE_DISCOVERY["issuer"],
        audience="client-123",
        email="ada@acme.com",
    )
    http_handler.handler = _google_discovery_handler(id_token=id_token, jwks=real_jwks)

    state = encode_state_token({"tenant_id": str(tenant_id), "provider": "google_workspace"})
    resp = await client.get(
        "/auth/sso/callback/google_workspace", params={"code": "authcode", "state": state}
    )
    assert resp.status_code == 502
