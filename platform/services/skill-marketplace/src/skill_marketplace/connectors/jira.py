"""Atlassian OAuth 2.0 (3LO) — a *user* token scoped to whatever Jira
projects the employee themselves can see. Atlassian's API is reached
through a `cloudId` rather than a per-tenant hostname, so the OAuth
exchange makes one extra call (`accessible-resources`) to resolve it —
stored in TokenSet.extra and handed back on every invoke, same idea as
Salesforce's instance_url.
"""

from datetime import UTC, datetime, timedelta

import httpx

from ..config import settings
from .base import Connector, ConnectorError, TokenSet, ToolSpec, has_real_value

_AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
_ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
_API_BASE = "https://api.atlassian.com"

_SCOPES = "read:jira-work write:jira-work offline_access"


class JiraConnector(Connector):
    skill_id = "jira"
    supports_refresh = True

    def is_configured(self) -> bool:
        return has_real_value(settings.jira_client_id)

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="jira_search_issues",
                description="Search Jira issues (JQL) in projects the employee can see.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "jql": {"type": "string", "description": "Jira Query Language string"},
                        "max_results": {"type": "integer", "description": "Default 20"},
                    },
                    "required": ["jql"],
                },
            ),
            ToolSpec(
                name="jira_create_issue",
                description="Create a Jira issue in a project the employee has access to.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "summary": {"type": "string"},
                        "issue_type": {"type": "string", "description": "e.g. Task, Bug"},
                        "description": {"type": "string"},
                    },
                    "required": ["project_key", "summary", "issue_type"],
                },
            ),
        ]

    def authorize_url(
        self, *, state: str, redirect_uri: str, tenant_config: dict | None = None
    ) -> str:
        params = httpx.QueryParams(
            {
                "audience": "api.atlassian.com",
                "client_id": settings.jira_client_id,
                "scope": _SCOPES,
                "redirect_uri": redirect_uri,
                "state": state,
                "response_type": "code",
                "prompt": "consent",
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
            json={
                "grant_type": "authorization_code",
                "client_id": settings.jira_client_id,
                "client_secret": settings.jira_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(f"Jira OAuth exchange failed: {body}")
        return await self._token_set_from_response(body, http=http)

    async def refresh(
        self, *, refresh_token: str, http: httpx.AsyncClient, tenant_config: dict | None = None
    ) -> TokenSet:
        resp = await http.post(
            _TOKEN_URL,
            json={
                "grant_type": "refresh_token",
                "client_id": settings.jira_client_id,
                "client_secret": settings.jira_client_secret,
                "refresh_token": refresh_token,
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(f"Jira token refresh failed: {body}")
        body.setdefault("refresh_token", refresh_token)
        return await self._token_set_from_response(body, http=http)

    async def _token_set_from_response(self, body: dict, *, http: httpx.AsyncClient) -> TokenSet:
        access_token = body["access_token"]
        resources_resp = await http.get(
            _ACCESSIBLE_RESOURCES_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        resources = resources_resp.json() if resources_resp.status_code < 400 else []
        if not resources:
            raise ConnectorError("Jira OAuth grant has no accessible Jira sites")
        site = resources[0]

        expires_in = body.get("expires_in")
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=expires_in) if expires_in is not None else None
        )

        return TokenSet(
            access_token=access_token,
            refresh_token=body.get("refresh_token"),
            expires_at=expires_at,
            scope=body.get("scope"),
            external_account=site.get("url"),
            extra={"cloud_id": site["id"]},
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
        cloud_id = extra.get("cloud_id")
        if not cloud_id:
            raise ConnectorError("Jira connection is missing its cloud_id — reconnect required")

        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        base = f"{_API_BASE}/ex/jira/{cloud_id}/rest/api/3"

        if tool_name == "jira_search_issues":
            resp = await http.get(
                f"{base}/search",
                params={
                    "jql": tool_input["jql"],
                    "maxResults": tool_input.get("max_results", 20),
                },
                headers=headers,
            )
        elif tool_name == "jira_create_issue":
            payload = {
                "fields": {
                    "project": {"key": tool_input["project_key"]},
                    "summary": tool_input["summary"],
                    "issuetype": {"name": tool_input["issue_type"]},
                }
            }
            if tool_input.get("description"):
                payload["fields"]["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": tool_input["description"]}],
                        }
                    ],
                }
            resp = await http.post(
                f"{base}/issue",
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
            )
        else:
            raise ConnectorError(f"Unknown Jira tool {tool_name!r}")

        body = resp.json()
        if resp.status_code >= 400:
            raise ConnectorError(f"Jira API error: {body}")
        return body
