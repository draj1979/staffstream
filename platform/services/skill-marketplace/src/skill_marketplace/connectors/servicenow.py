"""ServiceNow OAuth 2.0 — per-*instance*, unlike Slack/GitHub's one fixed
global endpoint: `https://{instance}.service-now.com`. The instance name
is a tenant-level fact (which ServiceNow instance this org uses), not a
per-employee one, so it comes from `TenantSkillEnablement.config` — set
once by an admin via `PUT /skills/servicenow/enablement`
(`{"instance": "acme"}`), same table Phase 8 already introduced for this
exact purpose. Every call still runs as the employee's own ServiceNow
user, with whatever the instance's own ACLs allow them to see.
"""

import httpx

from ..config import settings
from .base import Connector, ConnectorError, TokenSet, ToolSpec


def _require_instance(tenant_config: dict | None) -> str:
    instance = (tenant_config or {}).get("instance")
    if not instance:
        raise ConnectorError(
            "ServiceNow requires the tenant's instance name to be set in this skill's "
            "enablement config, e.g. PUT /skills/servicenow/enablement {\"config\": "
            '{"instance": "acme"}}'
        )
    return instance


class ServiceNowConnector(Connector):
    skill_id = "servicenow"

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="servicenow_search_incidents",
                description="Search incidents in the tenant's ServiceNow instance.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "ServiceNow encoded query (sysparm_query)",
                        },
                        "limit": {"type": "integer", "description": "Default 20"},
                    },
                },
            ),
            ToolSpec(
                name="servicenow_create_incident",
                description="Create an incident in the tenant's ServiceNow instance.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "short_description": {"type": "string"},
                        "description": {"type": "string"},
                        "urgency": {"type": "string", "description": "1 (high) - 3 (low)"},
                    },
                    "required": ["short_description"],
                },
            ),
        ]

    def authorize_url(
        self, *, state: str, redirect_uri: str, tenant_config: dict | None = None
    ) -> str:

        instance = _require_instance(tenant_config)
        params = httpx.QueryParams(
            {
                "response_type": "code",
                "client_id": settings.servicenow_client_id,
                "redirect_uri": redirect_uri,
                "state": state,
            }
        )
        return f"https://{instance}.service-now.com/oauth_auth.do?{params}"

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        http: httpx.AsyncClient,
        tenant_config: dict | None = None,
    ) -> TokenSet:

        instance = _require_instance(tenant_config)
        resp = await http.post(
            f"https://{instance}.service-now.com/oauth_token.do",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.servicenow_client_id,
                "client_secret": settings.servicenow_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(f"ServiceNow OAuth exchange failed: {body}")
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=None,
            scope=body.get("scope"),
            external_account=None,
            extra={"instance": instance},
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
        instance = extra.get("instance")
        if not instance:
            raise ConnectorError(
                "ServiceNow connection is missing its instance — reconnect required"
            )

        headers = {"Authorization": f"Bearer {access_token}"}
        base = f"https://{instance}.service-now.com/api/now/table/incident"

        if tool_name == "servicenow_search_incidents":
            params = {"sysparm_limit": tool_input.get("limit", 20)}
            if tool_input.get("query"):
                params["sysparm_query"] = tool_input["query"]
            resp = await http.get(base, params=params, headers=headers)
        elif tool_name == "servicenow_create_incident":
            payload = {"short_description": tool_input["short_description"]}
            if tool_input.get("description"):
                payload["description"] = tool_input["description"]
            if tool_input.get("urgency"):
                payload["urgency"] = tool_input["urgency"]
            resp = await http.post(base, json=payload, headers=headers)
        else:
            raise ConnectorError(f"Unknown ServiceNow tool {tool_name!r}")

        body = resp.json()
        if resp.status_code >= 400:
            raise ConnectorError(f"ServiceNow API error: {body}")
        return body
