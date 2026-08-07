"""HubSpot OAuth 2.0 — a *user* token scoped to the employee's own
HubSpot account permissions within the connected portal (HubSpot's
sharing model is portal-wide by default, but the token still carries the
individual user's own permission set and audit identity, not a shared
API key).
"""

from datetime import UTC, datetime, timedelta

import httpx

from ..config import settings
from .base import Connector, ConnectorError, TokenSet, ToolSpec

_AUTHORIZE_URL = "https://app.hubspot.com/oauth/authorize"
_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
_API_BASE = "https://api.hubapi.com"

_SCOPES = "crm.objects.contacts.read crm.objects.contacts.write"


class HubSpotConnector(Connector):
    skill_id = "hubspot"
    supports_refresh = True

    def is_configured(self) -> bool:
        return not settings.hubspot_client_id.startswith("not-set")

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="hubspot_search_contacts",
                description="Search HubSpot CRM contacts by email or name.",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            ),
            ToolSpec(
                name="hubspot_create_contact",
                description="Create a HubSpot CRM contact.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "email": {"type": "string"},
                        "firstname": {"type": "string"},
                        "lastname": {"type": "string"},
                    },
                    "required": ["email"],
                },
            ),
        ]

    def authorize_url(
        self, *, state: str, redirect_uri: str, tenant_config: dict | None = None
    ) -> str:
        params = httpx.QueryParams(
            {
                "client_id": settings.hubspot_client_id,
                "redirect_uri": redirect_uri,
                "scope": _SCOPES,
                "state": state,
            }
        )
        return f"{_AUTHORIZE_URL}?{params}"

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        http: httpx.AsyncClient,
        tenant_config: dict | None = None,
    ) -> TokenSet:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.hubspot_client_id,
                "client_secret": settings.hubspot_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(f"HubSpot OAuth exchange failed: {body}")
        return self._token_set_from_response(body)

    async def refresh(
        self, *, refresh_token: str, http: httpx.AsyncClient, tenant_config: dict | None = None
    ) -> TokenSet:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.hubspot_client_id,
                "client_secret": settings.hubspot_client_secret,
                "refresh_token": refresh_token,
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(f"HubSpot token refresh failed: {body}")
        body.setdefault("refresh_token", refresh_token)
        return self._token_set_from_response(body)

    def _token_set_from_response(self, body: dict) -> TokenSet:
        expires_in = body.get("expires_in", 1800)
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scope=None,
            external_account=None,
        )

    async def invoke(
        self,
        *,
        tool_name: str,
        tool_input: dict,
        access_token: str,
        http: httpx.AsyncClient,
        extra: dict | None = None,
    ) -> dict:
        headers = {"Authorization": f"Bearer {access_token}"}

        if tool_name == "hubspot_search_contacts":
            resp = await http.post(
                f"{_API_BASE}/crm/v3/objects/contacts/search",
                json={
                    "query": tool_input["query"],
                    "properties": ["email", "firstname", "lastname"],
                },
                headers=headers,
            )
        elif tool_name == "hubspot_create_contact":
            properties = {"email": tool_input["email"]}
            if tool_input.get("firstname"):
                properties["firstname"] = tool_input["firstname"]
            if tool_input.get("lastname"):
                properties["lastname"] = tool_input["lastname"]
            resp = await http.post(
                f"{_API_BASE}/crm/v3/objects/contacts",
                json={"properties": properties},
                headers=headers,
            )
        else:
            raise ConnectorError(f"Unknown HubSpot tool {tool_name!r}")

        body = resp.json()
        if resp.status_code >= 400:
            raise ConnectorError(f"HubSpot API error: {body}")
        return body
