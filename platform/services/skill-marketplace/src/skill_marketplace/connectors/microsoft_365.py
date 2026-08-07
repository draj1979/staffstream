"""Microsoft 365 (Outlook mail) via Microsoft Graph — a *delegated* user
token, so every call reads/sends as the employee's own mailbox (`/me/...`
Graph routes), never a shared mailbox or app-only credential. See
_microsoft.py for the shared OAuth mechanics with microsoft_teams.py.
"""

import httpx

from ..config import settings
from . import _microsoft
from .base import Connector, ConnectorError, TokenSet, ToolSpec

_SCOPES = "offline_access Mail.Read Mail.Send"


class Microsoft365Connector(Connector):
    skill_id = "microsoft_365"
    supports_refresh = True

    def is_configured(self) -> bool:
        return not settings.microsoft_client_id.startswith("not-set")

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="m365_list_mail",
                description="List recent messages in the employee's own Outlook inbox.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "top": {"type": "integer", "description": "Max messages, default 10"}
                    },
                },
            ),
            ToolSpec(
                name="m365_send_mail",
                description="Send an email from the employee's own Outlook account.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["to", "subject", "body"],
                },
            ),
        ]

    def authorize_url(
        self, *, state: str, redirect_uri: str, tenant_config: dict | None = None
    ) -> str:
        return _microsoft.build_authorize_url(
            client_id=settings.microsoft_client_id,
            scopes=_SCOPES,
            state=state,
            redirect_uri=redirect_uri,
        )

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        http: httpx.AsyncClient,
        tenant_config: dict | None = None,
    ) -> TokenSet:
        return await _microsoft.exchange_code(
            client_id=settings.microsoft_client_id,
            client_secret=settings.microsoft_client_secret,
            scopes=_SCOPES,
            code=code,
            redirect_uri=redirect_uri,
            http=http,
        )

    async def refresh(
        self, *, refresh_token: str, http: httpx.AsyncClient, tenant_config: dict | None = None
    ) -> TokenSet:
        return await _microsoft.refresh(
            client_id=settings.microsoft_client_id,
            client_secret=settings.microsoft_client_secret,
            scopes=_SCOPES,
            refresh_token=refresh_token,
            http=http,
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

        if tool_name == "m365_list_mail":
            resp = await http.get(
                f"{_microsoft.GRAPH_BASE}/me/messages",
                params={"$top": tool_input.get("top", 10)},
                headers=headers,
            )
        elif tool_name == "m365_send_mail":
            payload = {
                "message": {
                    "subject": tool_input["subject"],
                    "body": {"contentType": "Text", "content": tool_input["body"]},
                    "toRecipients": [{"emailAddress": {"address": tool_input["to"]}}],
                }
            }
            resp = await http.post(
                f"{_microsoft.GRAPH_BASE}/me/sendMail", json=payload, headers=headers
            )
            if resp.status_code == 202:  # sendMail returns 202 with no body
                return {"status": "sent"}
        else:
            raise ConnectorError(f"Unknown Microsoft 365 tool {tool_name!r}")

        if resp.status_code >= 400:
            raise ConnectorError(f"Microsoft 365 API error: {resp.text}")
        return resp.json()
