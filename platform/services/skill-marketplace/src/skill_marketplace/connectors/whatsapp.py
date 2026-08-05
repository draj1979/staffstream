"""WhatsApp Business Platform (Meta) — OAuth via Facebook Login for
Business. Unlike the other messaging connectors, WhatsApp Business
accounts are provisioned per phone number, and the `phone_number_id`
used to send messages is a tenant-level fact (which WABA/number this
org sends from), so it comes from `TenantSkillEnablement.config`
(`{"phone_number_id": "1234567890"}`), same pattern as ServiceNow's
`instance` / SAP's `sap_base_url`. The OAuth token itself is still
obtained per-employee (whoever connects becomes the sender of record for
messages they trigger), matching this platform's employee-consent model
even though the underlying WABA is shared infrastructure.
"""

import httpx

from ..config import settings
from .base import Connector, ConnectorError, TokenSet, ToolSpec

_AUTHORIZE_URL = "https://www.facebook.com/v21.0/dialog/oauth"
_TOKEN_URL = "https://graph.facebook.com/v21.0/oauth/access_token"
_GRAPH_BASE = "https://graph.facebook.com/v21.0"
_SCOPES = "whatsapp_business_messaging,whatsapp_business_management"


def _require_phone_number_id(tenant_config: dict | None) -> str:
    phone_number_id = (tenant_config or {}).get("phone_number_id")
    if not phone_number_id:
        raise ConnectorError(
            "WhatsApp requires the tenant's WhatsApp Business phone_number_id to be set in "
            "this skill's enablement config, e.g. PUT /skills/whatsapp/enablement {\"config\": "
            '{"phone_number_id": "1234567890"}}'
        )
    return phone_number_id


class WhatsAppConnector(Connector):
    skill_id = "whatsapp"

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="whatsapp_send_message",
                description=(
                    "Send a WhatsApp text message from the tenant's WhatsApp Business number."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient phone number, E.164 format",
                        },
                        "text": {"type": "string"},
                    },
                    "required": ["to", "text"],
                },
            ),
            ToolSpec(
                name="whatsapp_get_message_templates",
                description=(
                    "List approved message templates for the tenant's WhatsApp Business account."
                ),
                input_schema={"type": "object", "properties": {}},
            ),
        ]

    def authorize_url(
        self, *, state: str, redirect_uri: str, tenant_config: dict | None = None
    ) -> str:
        params = httpx.QueryParams(
            {
                "client_id": settings.whatsapp_client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": _SCOPES,
                "response_type": "code",
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
        phone_number_id = _require_phone_number_id(tenant_config)
        resp = await http.get(
            _TOKEN_URL,
            params={
                "client_id": settings.whatsapp_client_id,
                "client_secret": settings.whatsapp_client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(f"WhatsApp OAuth exchange failed: {body}")
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=None,  # long-lived tokens; no refresh flow, must re-auth on expiry
            expires_at=None,
            scope=body.get("scope"),
            external_account=None,
            extra={"phone_number_id": phone_number_id},
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
        phone_number_id = extra.get("phone_number_id")
        if not phone_number_id:
            raise ConnectorError(
                "WhatsApp connection is missing its phone_number_id — reconnect required"
            )

        headers = {"Authorization": f"Bearer {access_token}"}

        if tool_name == "whatsapp_send_message":
            payload = {
                "messaging_product": "whatsapp",
                "to": tool_input["to"],
                "type": "text",
                "text": {"body": tool_input["text"]},
            }
            resp = await http.post(
                f"{_GRAPH_BASE}/{phone_number_id}/messages", json=payload, headers=headers
            )
        elif tool_name == "whatsapp_get_message_templates":
            resp = await http.get(
                f"{_GRAPH_BASE}/{phone_number_id}/message_templates", headers=headers
            )
        else:
            raise ConnectorError(f"Unknown WhatsApp tool {tool_name!r}")

        body = resp.json()
        if resp.status_code >= 400:
            raise ConnectorError(f"WhatsApp API error: {body}")
        return body
