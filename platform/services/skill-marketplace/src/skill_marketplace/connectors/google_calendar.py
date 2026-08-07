"""Google OAuth2 with the `calendar.events` scope against the employee's
own account (`access_type=offline` + `prompt=consent` so a refresh_token
comes back on the first grant). Every call reads/writes the `primary`
calendar of whichever account the token belongs to — the employee's own,
never a shared or service-level calendar.
"""

from datetime import UTC, datetime, timedelta

import httpx

from ..config import settings
from .base import Connector, ConnectorError, TokenSet, ToolSpec

_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

_SCOPE = "https://www.googleapis.com/auth/calendar.events"


class GoogleCalendarConnector(Connector):
    skill_id = "google_calendar"
    supports_refresh = True

    def is_configured(self) -> bool:
        return not settings.google_client_id.startswith("not-set")

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="calendar_list_events",
                description="List upcoming events on the employee's own Google Calendar.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "time_min": {
                            "type": "string",
                            "description": "RFC3339 lower bound, e.g. 2026-08-05T00:00:00Z",
                        },
                        "time_max": {
                            "type": "string",
                            "description": "RFC3339 upper bound",
                        },
                        "max_results": {"type": "integer", "description": "Default 10"},
                    },
                    "required": ["time_min", "time_max"],
                },
            ),
            ToolSpec(
                name="calendar_create_event",
                description="Create an event on the employee's own Google Calendar.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "start": {"type": "string", "description": "RFC3339 start datetime"},
                        "end": {"type": "string", "description": "RFC3339 end datetime"},
                        "description": {"type": "string"},
                        "attendee_emails": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["summary", "start", "end"],
                },
            ),
        ]

    def authorize_url(
        self, *, state: str, redirect_uri: str, tenant_config: dict | None = None
    ) -> str:
        params = httpx.QueryParams(
            {
                "client_id": settings.google_client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": _SCOPE,
                "access_type": "offline",
                "prompt": "consent",
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
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(
                f"Google OAuth exchange failed: {body.get('error_description', body)}"
            )
        return await self._token_set_from_response(body, http=http)

    async def refresh(
        self, *, refresh_token: str, http: httpx.AsyncClient, tenant_config: dict | None = None
    ) -> TokenSet:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(
                f"Google token refresh failed: {body.get('error_description', body)}"
            )
        # Google's refresh response omits refresh_token (it doesn't
        # rotate) — carry the existing one forward.
        body.setdefault("refresh_token", refresh_token)
        return await self._token_set_from_response(body, http=http)

    async def _token_set_from_response(self, body: dict, *, http: httpx.AsyncClient) -> TokenSet:
        expires_in = body.get("expires_in")
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=expires_in) if expires_in is not None else None
        )

        external_account = None
        try:
            userinfo = await http.get(
                _USERINFO_URL, headers={"Authorization": f"Bearer {body['access_token']}"}
            )
            if userinfo.status_code < 400:
                external_account = userinfo.json().get("email")
        except httpx.HTTPError:
            pass  # display-only metadata; never fail the connection over it

        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=expires_at,
            scope=body.get("scope"),
            external_account=external_account,
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

        if tool_name == "calendar_list_events":
            resp = await http.get(
                _CALENDAR_EVENTS_URL,
                params={
                    "timeMin": tool_input["time_min"],
                    "timeMax": tool_input["time_max"],
                    "maxResults": tool_input.get("max_results", 10),
                    "singleEvents": "true",
                    "orderBy": "startTime",
                },
                headers=headers,
            )
        elif tool_name == "calendar_create_event":
            payload = {
                "summary": tool_input["summary"],
                "start": {"dateTime": tool_input["start"]},
                "end": {"dateTime": tool_input["end"]},
            }
            if tool_input.get("description"):
                payload["description"] = tool_input["description"]
            if tool_input.get("attendee_emails"):
                payload["attendees"] = [{"email": e} for e in tool_input["attendee_emails"]]
            resp = await http.post(_CALENDAR_EVENTS_URL, json=payload, headers=headers)
        else:
            raise ConnectorError(f"Unknown Google Calendar tool {tool_name!r}")

        body = resp.json()
        if resp.status_code >= 400:
            raise ConnectorError(f"Google Calendar API error: {body.get('error', body)}")
        return body
