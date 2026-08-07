"""Microsoft Teams via Microsoft Graph — a *delegated* user token, so
every call runs as the employee against whatever teams/channels they're
already a member of. See _microsoft.py for the shared OAuth mechanics.
"""

import httpx

from ..config import settings
from . import _microsoft
from .base import Connector, ConnectorError, TokenSet, ToolSpec, has_real_value

_SCOPES = "offline_access ChannelMessage.Read.All ChannelMessage.Send Team.ReadBasic.All"


class MicrosoftTeamsConnector(Connector):
    skill_id = "microsoft_teams"
    supports_refresh = True

    def is_configured(self) -> bool:
        return has_real_value(settings.microsoft_client_id)

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="teams_list_channel_messages",
                description=(
                    "Read recent messages from a Microsoft Teams channel the employee belongs to."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "team_id": {"type": "string"},
                        "channel_id": {"type": "string"},
                    },
                    "required": ["team_id", "channel_id"],
                },
            ),
            ToolSpec(
                name="teams_send_channel_message",
                description="Post a message to a Microsoft Teams channel the employee belongs to.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "team_id": {"type": "string"},
                        "channel_id": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["team_id", "channel_id", "text"],
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
        team_id, channel_id = tool_input.get("team_id"), tool_input.get("channel_id")

        if tool_name == "teams_list_channel_messages":
            resp = await http.get(
                f"{_microsoft.GRAPH_BASE}/teams/{team_id}/channels/{channel_id}/messages",
                headers=headers,
            )
        elif tool_name == "teams_send_channel_message":
            resp = await http.post(
                f"{_microsoft.GRAPH_BASE}/teams/{team_id}/channels/{channel_id}/messages",
                json={"body": {"content": tool_input["text"]}},
                headers=headers,
            )
        else:
            raise ConnectorError(f"Unknown Microsoft Teams tool {tool_name!r}")

        body = resp.json()
        if resp.status_code >= 400:
            raise ConnectorError(f"Microsoft Teams API error: {body}")
        return body
