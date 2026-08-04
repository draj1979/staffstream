import httpx
import pytest
from skill_marketplace.connectors.base import ConnectorError
from skill_marketplace.connectors.google_calendar import GoogleCalendarConnector
from skill_marketplace.connectors.slack import SlackConnector


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---- Slack ----------------------------------------------------------------


def test_slack_authorize_url_uses_user_scope_not_bot_scope():
    connector = SlackConnector()
    url = connector.authorize_url(state="s1", redirect_uri="https://x/cb")
    assert "user_scope=" in url
    assert "&scope=" not in url  # no bot-scope param anywhere
    assert "state=s1" in url


async def test_slack_exchange_code_uses_authed_user_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/oauth.v2.access"
        return httpx.Response(
            200,
            json={
                "ok": True,
                "authed_user": {
                    "id": "U123",
                    "access_token": "xoxp-user-token",
                    "scope": "channels:history,chat:write",
                },
            },
        )

    connector = SlackConnector()
    async with _mock_client(handler) as http:
        tokens = await connector.exchange_code(code="c1", redirect_uri="https://x/cb", http=http)

    assert tokens.access_token == "xoxp-user-token"
    assert tokens.external_account == "U123"
    assert tokens.refresh_token is None


async def test_slack_exchange_code_raises_on_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "error": "invalid_code"})

    connector = SlackConnector()
    async with _mock_client(handler) as http:
        with pytest.raises(ConnectorError, match="invalid_code"):
            await connector.exchange_code(code="bad", redirect_uri="https://x/cb", http=http)


async def test_slack_invoke_post_message_uses_bearer_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True, "ts": "123.456"})

    connector = SlackConnector()
    async with _mock_client(handler) as http:
        result = await connector.invoke(
            tool_name="slack_post_message",
            tool_input={"channel_id": "C1", "text": "hello"},
            access_token="xoxp-abc",
            http=http,
        )

    assert seen["auth"] == "Bearer xoxp-abc"
    assert b"hello" in seen["body"]
    assert result["ok"] is True


async def test_slack_invoke_unknown_tool_raises():
    connector = SlackConnector()
    async with _mock_client(lambda r: httpx.Response(200)) as http:
        with pytest.raises(ConnectorError):
            await connector.invoke(
                tool_name="slack_delete_workspace",
                tool_input={},
                access_token="xoxp-abc",
                http=http,
            )


async def test_slack_invoke_raises_on_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "error": "channel_not_found"})

    connector = SlackConnector()
    async with _mock_client(handler) as http:
        with pytest.raises(ConnectorError, match="channel_not_found"):
            await connector.invoke(
                tool_name="slack_read_channel_messages",
                tool_input={"channel_id": "C-does-not-exist"},
                access_token="xoxp-abc",
                http=http,
            )


# ---- Google Calendar --------------------------------------------------------


def test_google_authorize_url_requests_offline_access():
    connector = GoogleCalendarConnector()
    url = connector.authorize_url(state="s1", redirect_uri="https://x/cb")
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "calendar.events" in url


async def test_google_exchange_code_fetches_userinfo_email():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "ya29.access",
                    "refresh_token": "1//refresh",
                    "expires_in": 3600,
                    "scope": "https://www.googleapis.com/auth/calendar.events",
                },
            )
        if request.url.path == "/v1/userinfo":
            return httpx.Response(200, json={"email": "employee@example.com"})
        raise AssertionError(f"unexpected call to {request.url}")

    connector = GoogleCalendarConnector()
    async with _mock_client(handler) as http:
        tokens = await connector.exchange_code(code="c1", redirect_uri="https://x/cb", http=http)

    assert tokens.access_token == "ya29.access"
    assert tokens.refresh_token == "1//refresh"
    assert tokens.external_account == "employee@example.com"
    assert tokens.expires_at is not None


async def test_google_exchange_code_raises_on_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error_description": "bad code"})

    connector = GoogleCalendarConnector()
    async with _mock_client(handler) as http:
        with pytest.raises(ConnectorError, match="bad code"):
            await connector.exchange_code(code="bad", redirect_uri="https://x/cb", http=http)


async def test_google_refresh_carries_forward_existing_refresh_token_when_omitted():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "ya29.new", "expires_in": 3600})
        return httpx.Response(200, json={})  # userinfo call

    connector = GoogleCalendarConnector()
    async with _mock_client(handler) as http:
        tokens = await connector.refresh(refresh_token="1//original", http=http)

    assert tokens.access_token == "ya29.new"
    assert tokens.refresh_token == "1//original"


async def test_google_invoke_create_event_builds_expected_payload():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"id": "evt1", "htmlLink": "https://calendar/evt1"})

    connector = GoogleCalendarConnector()
    async with _mock_client(handler) as http:
        result = await connector.invoke(
            tool_name="calendar_create_event",
            tool_input={
                "summary": "Sync",
                "start": "2026-08-10T10:00:00Z",
                "end": "2026-08-10T10:30:00Z",
                "attendee_emails": ["a@example.com"],
            },
            access_token="ya29.abc",
            http=http,
        )

    assert seen["auth"] == "Bearer ya29.abc"
    assert b"Sync" in seen["body"]
    assert b"a@example.com" in seen["body"]
    assert result["id"] == "evt1"


async def test_google_invoke_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "insufficient scope"}})

    connector = GoogleCalendarConnector()
    async with _mock_client(handler) as http:
        with pytest.raises(ConnectorError, match="insufficient scope"):
            await connector.invoke(
                tool_name="calendar_list_events",
                tool_input={"time_min": "2026-08-01T00:00:00Z", "time_max": "2026-08-02T00:00:00Z"},
                access_token="ya29.abc",
                http=http,
            )
