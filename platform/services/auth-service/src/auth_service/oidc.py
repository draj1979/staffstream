"""Generic OIDC helper shared by every SSO provider — Google Workspace
and Auth0 are both standard OpenID Connect, so one implementation covers
both; a provider only differs in its discovery URL and (for Google) the
optional `hd` hosted-domain restriction. Every network call takes the
httpx client to use rather than making its own, so tests can swap in a
`httpx.MockTransport` — including the JWKS fetch, so id_token signature
verification is exercised for real against a test keypair, not mocked
away.
"""

import json

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm


class OIDCError(Exception):
    """Raised for any failure in the discovery -> exchange -> verify
    chain — an unknown provider, a missing issuer_domain, a failed token
    exchange, or a signature/claims verification failure."""


def discovery_url(provider: str, *, issuer_domain: str | None) -> str:
    if provider == "google_workspace":
        return "https://accounts.google.com/.well-known/openid-configuration"
    if provider == "auth0":
        if not issuer_domain:
            raise OIDCError("Auth0 SSO requires issuer_domain to be configured")
        return f"https://{issuer_domain}/.well-known/openid-configuration"
    raise OIDCError(f"Unknown SSO provider {provider!r}")


async def fetch_discovery(url: str, *, http: httpx.AsyncClient) -> dict:
    resp = await http.get(url)
    if resp.status_code >= 400:
        raise OIDCError(f"OIDC discovery fetch failed: {resp.status_code} {resp.text}")
    return resp.json()


def build_authorize_url(
    discovery: dict,
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    hosted_domain: str | None = None,
) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    if hosted_domain:
        params["hd"] = hosted_domain
    return f"{discovery['authorization_endpoint']}?{httpx.QueryParams(params)}"


async def exchange_code(
    discovery: dict,
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    http: httpx.AsyncClient,
) -> dict:
    resp = await http.post(
        discovery["token_endpoint"],
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    body = resp.json()
    if "id_token" not in body:
        raise OIDCError(f"OIDC token exchange failed: {body.get('error_description', body)}")
    return body


async def fetch_jwks(jwks_uri: str, *, http: httpx.AsyncClient) -> dict:
    resp = await http.get(jwks_uri)
    if resp.status_code >= 400:
        raise OIDCError(f"JWKS fetch failed: {resp.status_code} {resp.text}")
    return resp.json()


def _find_signing_key(jwks: dict, kid: str | None) -> dict:
    keys = jwks.get("keys", [])
    if not keys:
        raise OIDCError("JWKS document has no keys")
    if kid is None:
        return keys[0]
    for key in keys:
        if key.get("kid") == kid:
            return key
    raise OIDCError(f"No JWKS key matching kid={kid!r}")


def verify_id_token(id_token: str, *, jwks: dict, issuer: str, audience: str) -> dict:
    """Verifies the id_token's RS256 signature against the fetched JWKS,
    plus standard issuer/audience/expiry claims — this is the real
    authentication step of the whole flow; everything before it (state,
    code exchange) just gets us to this one signature check."""
    try:
        header = jwt.get_unverified_header(id_token)
    except jwt.PyJWTError as exc:
        raise OIDCError(f"Malformed id_token: {exc}") from exc

    key_data = _find_signing_key(jwks, header.get("kid"))
    try:
        public_key = RSAAlgorithm.from_jwk(json.dumps(key_data))
        return jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
        )
    except jwt.PyJWTError as exc:
        raise OIDCError(f"id_token verification failed: {exc}") from exc
