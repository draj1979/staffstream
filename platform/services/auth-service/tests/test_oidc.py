import json
import time
import uuid

import httpx
import jwt
import pytest
from auth_service import oidc
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm


def _generate_keypair_and_jwks(kid: str = "test-key-1"):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = kid
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return private_key, {"keys": [jwk]}


def _sign_id_token(private_key, *, kid, issuer, audience, email, extra_claims=None):
    now = int(time.time())
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": str(uuid.uuid4()),
        "email": email,
        "iat": now,
        "exp": now + 300,
    }
    claims.update(extra_claims or {})
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def test_discovery_url_for_known_providers():
    assert (
        oidc.discovery_url("google_workspace", issuer_domain=None)
        == "https://accounts.google.com/.well-known/openid-configuration"
    )
    assert (
        oidc.discovery_url("auth0", issuer_domain="acme.us.auth0.com")
        == "https://acme.us.auth0.com/.well-known/openid-configuration"
    )


def test_discovery_url_auth0_without_domain_raises():
    with pytest.raises(oidc.OIDCError):
        oidc.discovery_url("auth0", issuer_domain=None)


def test_discovery_url_unknown_provider_raises():
    with pytest.raises(oidc.OIDCError):
        oidc.discovery_url("okta", issuer_domain=None)


def test_verify_id_token_accepts_valid_signature_and_claims():
    private_key, jwks = _generate_keypair_and_jwks()
    token = _sign_id_token(
        private_key,
        kid="test-key-1",
        issuer="https://accounts.google.com",
        audience="client-123",
        email="ada@acme.com",
    )
    claims = oidc.verify_id_token(
        token, jwks=jwks, issuer="https://accounts.google.com", audience="client-123"
    )
    assert claims["email"] == "ada@acme.com"


def test_verify_id_token_rejects_wrong_issuer():
    private_key, jwks = _generate_keypair_and_jwks()
    token = _sign_id_token(
        private_key,
        kid="test-key-1",
        issuer="https://evil.example",
        audience="client-123",
        email="ada@acme.com",
    )
    with pytest.raises(oidc.OIDCError):
        oidc.verify_id_token(
            token, jwks=jwks, issuer="https://accounts.google.com", audience="client-123"
        )


def test_verify_id_token_rejects_wrong_audience():
    private_key, jwks = _generate_keypair_and_jwks()
    token = _sign_id_token(
        private_key,
        kid="test-key-1",
        issuer="https://accounts.google.com",
        audience="someone-elses-client",
        email="ada@acme.com",
    )
    with pytest.raises(oidc.OIDCError):
        oidc.verify_id_token(
            token, jwks=jwks, issuer="https://accounts.google.com", audience="client-123"
        )


def test_verify_id_token_rejects_signature_from_untrusted_key():
    _, jwks = _generate_keypair_and_jwks(kid="test-key-1")
    forged_key, _ = _generate_keypair_and_jwks(kid="test-key-1")
    token = _sign_id_token(
        forged_key,
        kid="test-key-1",
        issuer="https://accounts.google.com",
        audience="client-123",
        email="ada@acme.com",
    )
    with pytest.raises(oidc.OIDCError):
        oidc.verify_id_token(
            token, jwks=jwks, issuer="https://accounts.google.com", audience="client-123"
        )


def test_verify_id_token_rejects_expired_token():
    private_key, jwks = _generate_keypair_and_jwks()
    token = _sign_id_token(
        private_key,
        kid="test-key-1",
        issuer="https://accounts.google.com",
        audience="client-123",
        email="ada@acme.com",
        extra_claims={"exp": int(time.time()) - 60, "iat": int(time.time()) - 120},
    )
    with pytest.raises(oidc.OIDCError):
        oidc.verify_id_token(
            token, jwks=jwks, issuer="https://accounts.google.com", audience="client-123"
        )


def test_build_authorize_url_includes_hosted_domain_for_google():
    discovery = {"authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth"}
    url = oidc.build_authorize_url(
        discovery,
        client_id="client-123",
        redirect_uri="https://x/callback",
        state="s1",
        hosted_domain="acme.com",
    )
    assert "hd=acme.com" in url
    assert "state=s1" in url


async def test_fetch_discovery_and_jwks_via_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        if "openid-configuration" in str(request.url):
            return httpx.Response(200, json={"issuer": "https://accounts.google.com"})
        return httpx.Response(200, json={"keys": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        discovery = await oidc.fetch_discovery(
            "https://accounts.google.com/.well-known/openid-configuration", http=http
        )
        assert discovery["issuer"] == "https://accounts.google.com"

        jwks = await oidc.fetch_jwks("https://accounts.google.com/oauth2/v3/certs", http=http)
        assert jwks == {"keys": []}


async def test_exchange_code_raises_when_no_id_token_in_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error_description": "invalid_grant"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(oidc.OIDCError, match="invalid_grant"):
            await oidc.exchange_code(
                {"token_endpoint": "https://x/token"},
                client_id="c",
                client_secret="s",
                code="bad",
                redirect_uri="https://x/callback",
                http=http,
            )
