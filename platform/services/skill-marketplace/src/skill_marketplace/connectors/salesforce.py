"""Salesforce OAuth 2.0 web-server flow — a *user* token, so record
access follows the employee's own Salesforce profile and sharing rules,
not a service account with org-wide visibility. Every org gets its own
`instance_url` back in the token response (Salesforce doesn't put it in
the authorize/token URLs the way ServiceNow's instance subdomain works)
— stored in TokenSet.extra, same idea as Jira's cloudId.
"""

from datetime import UTC, datetime, timedelta

import httpx

from ..config import settings
from .base import Connector, ConnectorError, TokenSet, ToolSpec

_AUTHORIZE_URL = "https://login.salesforce.com/services/oauth2/authorize"
_TOKEN_URL = "https://login.salesforce.com/services/oauth2/token"
_API_VERSION = "v61.0"

_SCOPES = "api refresh_token"


class SalesforceConnector(Connector):
    skill_id = "salesforce"
    supports_refresh = True

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="salesforce_query",
                description="Run a SOQL query against the employee's own Salesforce org.",
                input_schema={
                    "type": "object",
                    "properties": {"soql": {"type": "string", "description": "SOQL query"}},
                    "required": ["soql"],
                },
            ),
            ToolSpec(
                name="salesforce_create_record",
                description="Create a record (e.g. Lead, Contact, Opportunity) in Salesforce.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "sobject": {"type": "string", "description": "e.g. Lead, Contact"},
                        "fields": {"type": "object", "description": "Field name -> value"},
                    },
                    "required": ["sobject", "fields"],
                },
            ),
        ]

    def authorize_url(
        self, *, state: str, redirect_uri: str, tenant_config: dict | None = None
    ) -> str:
        params = httpx.QueryParams(
            {
                "response_type": "code",
                "client_id": settings.salesforce_client_id,
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
                "client_id": settings.salesforce_client_id,
                "client_secret": settings.salesforce_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(f"Salesforce OAuth exchange failed: {body}")
        return self._token_set_from_response(body)

    async def refresh(
        self, *, refresh_token: str, http: httpx.AsyncClient, tenant_config: dict | None = None
    ) -> TokenSet:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.salesforce_client_id,
                "client_secret": settings.salesforce_client_secret,
                "refresh_token": refresh_token,
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(f"Salesforce token refresh failed: {body}")
        body.setdefault("refresh_token", refresh_token)
        return self._token_set_from_response(body)

    def _token_set_from_response(self, body: dict) -> TokenSet:
        # Salesforce access tokens are typically valid ~2h but don't
        # return expires_in; refresh reactively on a 401 isn't wired up
        # here, so this connector relies on its refresh_token being used
        # proactively is not guaranteed — a known simplification, see
        # README. Setting expires_at conservatively short is safer than
        # treating it as never-expiring.
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(minutes=90),
            scope=body.get("scope"),
            external_account=body.get("id"),  # identity URL
            extra={"instance_url": body["instance_url"]},
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
        extra = extra or {}
        instance_url = extra.get("instance_url")
        if not instance_url:
            raise ConnectorError(
                "Salesforce connection is missing its instance_url — reconnect required"
            )

        headers = {"Authorization": f"Bearer {access_token}"}
        base = f"{instance_url}/services/data/{_API_VERSION}"

        if tool_name == "salesforce_query":
            resp = await http.get(
                f"{base}/query", params={"q": tool_input["soql"]}, headers=headers
            )
        elif tool_name == "salesforce_create_record":
            resp = await http.post(
                f"{base}/sobjects/{tool_input['sobject']}",
                json=tool_input["fields"],
                headers=headers,
            )
        else:
            raise ConnectorError(f"Unknown Salesforce tool {tool_name!r}")

        body = resp.json()
        if resp.status_code >= 400:
            raise ConnectorError(f"Salesforce API error: {body}")
        return body
