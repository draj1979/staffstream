"""Slack OAuth v2 with a *user* token (`user_scope`, not `scope`) — every
call this connector makes runs as the employee themselves, against
whatever channels their own Slack account can see. There is no bot token
anywhere in this connector; a channel the employee isn't a member of is a
channel this connector cannot read or post to, by construction of the
Slack API itself, not by any check this code has to remember to make.
"""

import httpx

from ..config import settings
from .base import Connector, ConnectorError, TokenSet, ToolSpec

_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
_API_BASE = "https://slack.com/api"

# channels:read/groups:read for listing, *:history for reading, chat:write
# for posting — the narrowest set that covers both tools below.
_USER_SCOPES = "channels:history,channels:read,groups:history,groups:read,chat:write"


class SlackConnector(Connector):
    skill_id = "slack"

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="slack_list_channels",
                description=(
                    "List Slack channels the employee is a member of (public and private)."
                ),
                input_schema={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="slack_read_channel_messages",
                description="Read recent messages from a Slack channel the employee belongs to.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "channel_id": {"type": "string", "description": "Slack channel ID"},
                        "limit": {
                            "type": "integer",
                            "description": "Max messages to return (default 20)",
                        },
                    },
                    "required": ["channel_id"],
                },
            ),
            ToolSpec(
                name="slack_post_message",
                description="Post a message to a Slack channel the employee belongs to.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "channel_id": {"type": "string", "description": "Slack channel ID"},
                        "text": {"type": "string", "description": "Message text"},
                    },
                    "required": ["channel_id", "text"],
                },
            ),
        ]

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        params = httpx.QueryParams(
            {
                "client_id": settings.slack_client_id,
                "user_scope": _USER_SCOPES,
                "redirect_uri": redirect_uri,
                "state": state,
            }
        )
        return f"{_AUTHORIZE_URL}?{params}"

    async def exchange_code(
        self, *, code: str, redirect_uri: str, http: httpx.AsyncClient
    ) -> TokenSet:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "client_id": settings.slack_client_id,
                "client_secret": settings.slack_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        body = resp.json()
        if not body.get("ok"):
            raise ConnectorError(f"Slack OAuth exchange failed: {body.get('error', 'unknown')}")

        authed_user = body.get("authed_user", {})
        access_token = authed_user.get("access_token")
        if not access_token:
            raise ConnectorError("Slack OAuth exchange did not return a user access token")

        return TokenSet(
            access_token=access_token,
            refresh_token=None,  # classic Slack user tokens don't expire/rotate
            expires_at=None,
            scope=authed_user.get("scope"),
            external_account=authed_user.get("id"),
        )

    async def invoke(
        self, *, tool_name: str, tool_input: dict, access_token: str, http: httpx.AsyncClient
    ) -> dict:
        headers = {"Authorization": f"Bearer {access_token}"}

        if tool_name == "slack_list_channels":
            resp = await http.get(
                f"{_API_BASE}/users.conversations",
                params={"types": "public_channel,private_channel"},
                headers=headers,
            )
        elif tool_name == "slack_read_channel_messages":
            resp = await http.get(
                f"{_API_BASE}/conversations.history",
                params={
                    "channel": tool_input["channel_id"],
                    "limit": tool_input.get("limit", 20),
                },
                headers=headers,
            )
        elif tool_name == "slack_post_message":
            resp = await http.post(
                f"{_API_BASE}/chat.postMessage",
                json={"channel": tool_input["channel_id"], "text": tool_input["text"]},
                headers=headers,
            )
        else:
            raise ConnectorError(f"Unknown Slack tool {tool_name!r}")

        body = resp.json()
        if not body.get("ok"):
            raise ConnectorError(f"Slack API error: {body.get('error', 'unknown')}")
        return body
