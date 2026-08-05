"""Shared OAuth mechanics for the two Microsoft connectors (Teams,
Microsoft 365) — both go through the same Microsoft identity platform
app registration and Graph API, differing only in scopes and which Graph
endpoints they call. Not a public connector itself, just the plumbing
`microsoft_teams.py` and `microsoft_365.py` both need.

Uses the "common" multi-tenant authorize endpoint (works for any Entra ID
directory, not one fixed org) rather than requiring a per-tenant Azure AD
tenant ID up front — an employee's own consent during the OAuth flow is
what actually scopes access, same as every other connector here.
"""

from datetime import UTC, datetime, timedelta

import httpx

from .base import ConnectorError, TokenSet

AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def build_authorize_url(
    *, client_id: str, scopes: str, state: str, redirect_uri: str
) -> str:
    params = httpx.QueryParams(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "response_mode": "query",
            "scope": scopes,
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{params}"


async def exchange_code(
    *,
    client_id: str,
    client_secret: str,
    scopes: str,
    code: str,
    redirect_uri: str,
    http: httpx.AsyncClient,
) -> TokenSet:
    resp = await http.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "scope": scopes,
        },
    )
    body = resp.json()
    if "access_token" not in body:
        raise ConnectorError(f"Microsoft OAuth exchange failed: {body}")
    return await _token_set_from_response(body, http=http)


async def refresh(
    *, client_id: str, client_secret: str, scopes: str, refresh_token: str, http: httpx.AsyncClient
) -> TokenSet:
    resp = await http.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": scopes,
        },
    )
    body = resp.json()
    if "access_token" not in body:
        raise ConnectorError(f"Microsoft token refresh failed: {body}")
    body.setdefault("refresh_token", refresh_token)
    return await _token_set_from_response(body, http=http)


async def _token_set_from_response(body: dict, *, http: httpx.AsyncClient) -> TokenSet:
    expires_in = body.get("expires_in")
    expires_at = (
        datetime.now(UTC) + timedelta(seconds=expires_in) if expires_in is not None else None
    )

    external_account = None
    try:
        me = await http.get(
            f"{GRAPH_BASE}/me", headers={"Authorization": f"Bearer {body['access_token']}"}
        )
        if me.status_code < 400:
            external_account = me.json().get("userPrincipalName")
    except httpx.HTTPError:
        pass  # display-only metadata; never fail the connection over it

    return TokenSet(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        expires_at=expires_at,
        scope=body.get("scope"),
        external_account=external_account,
    )
