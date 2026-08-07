"""Tests for the 10 Phase 10 connectors. Each connector gets: an
authorize_url smoke test, a successful exchange_code test, an error-path
test, and an invoke test (plus a tenant_config-required test for the
per-tenant-instance connectors: ServiceNow, SAP, Oracle, WhatsApp)."""

import httpx
import pytest
from skill_marketplace.connectors.base import ConnectorError
from skill_marketplace.connectors.github import GitHubConnector
from skill_marketplace.connectors.hubspot import HubSpotConnector
from skill_marketplace.connectors.jira import JiraConnector
from skill_marketplace.connectors.microsoft_365 import Microsoft365Connector
from skill_marketplace.connectors.microsoft_teams import MicrosoftTeamsConnector
from skill_marketplace.connectors.oracle import OracleConnector
from skill_marketplace.connectors.salesforce import SalesforceConnector
from skill_marketplace.connectors.sap import SapConnector
from skill_marketplace.connectors.servicenow import ServiceNowConnector
from skill_marketplace.connectors.whatsapp import WhatsAppConnector


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---- Jira -------------------------------------------------------------


def test_jira_authorize_url_requests_offline_access():
    connector = JiraConnector()
    url = connector.authorize_url(state="s1", redirect_uri="https://x/cb")
    assert "audience=api.atlassian.com" in url
    assert "offline_access" in url
    assert "state=s1" in url


async def test_jira_exchange_code_resolves_cloud_id():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "jira-tok",
                    "refresh_token": "jira-refresh",
                    "expires_in": 3600,
                },
            )
        if request.url.path == "/oauth/token/accessible-resources":
            return httpx.Response(200, json=[{"id": "cloud-123", "url": "https://acme.atlassian.net"}])
        raise AssertionError(f"unexpected call to {request.url}")

    connector = JiraConnector()
    async with _mock_client(handler) as http:
        tokens = await connector.exchange_code(code="c1", redirect_uri="https://x/cb", http=http)

    assert tokens.access_token == "jira-tok"
    assert tokens.extra == {"cloud_id": "cloud-123"}
    assert tokens.external_account == "https://acme.atlassian.net"


async def test_jira_exchange_code_raises_when_no_accessible_sites():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "jira-tok"})
        return httpx.Response(200, json=[])

    connector = JiraConnector()
    async with _mock_client(handler) as http:
        with pytest.raises(ConnectorError, match="no accessible Jira sites"):
            await connector.exchange_code(code="c1", redirect_uri="https://x/cb", http=http)


async def test_jira_invoke_requires_cloud_id():
    connector = JiraConnector()
    async with _mock_client(lambda r: httpx.Response(200)) as http:
        with pytest.raises(ConnectorError, match="reconnect required"):
            await connector.invoke(
                tool_name="jira_search_issues",
                tool_input={"jql": "project = X"},
                access_token="tok",
                http=http,
                extra={},
            )


async def test_jira_invoke_search_issues():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "cloud-123" in str(request.url)
        return httpx.Response(200, json={"issues": []})

    connector = JiraConnector()
    async with _mock_client(handler) as http:
        result = await connector.invoke(
            tool_name="jira_search_issues",
            tool_input={"jql": "project = X"},
            access_token="tok",
            http=http,
            extra={"cloud_id": "cloud-123"},
        )
    assert result == {"issues": []}


# ---- GitHub -------------------------------------------------------------


def test_github_authorize_url_has_repo_scope():
    connector = GitHubConnector()
    url = connector.authorize_url(state="s1", redirect_uri="https://x/cb")
    assert "scope=repo" in url


async def test_github_exchange_code_fetches_login():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "gh-tok", "scope": "repo"})
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "octocat"})
        raise AssertionError(f"unexpected call to {request.url}")

    connector = GitHubConnector()
    async with _mock_client(handler) as http:
        tokens = await connector.exchange_code(code="c1", redirect_uri="https://x/cb", http=http)

    assert tokens.access_token == "gh-tok"
    assert tokens.external_account == "octocat"
    assert tokens.refresh_token is None


async def test_github_exchange_code_raises_on_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "bad_verification_code"})

    connector = GitHubConnector()
    async with _mock_client(handler) as http:
        with pytest.raises(ConnectorError, match="bad_verification_code"):
            await connector.exchange_code(code="bad", redirect_uri="https://x/cb", http=http)


async def test_github_invoke_list_issues():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/acme/widgets/issues"
        return httpx.Response(200, json=[{"number": 1}])

    connector = GitHubConnector()
    async with _mock_client(handler) as http:
        result = await connector.invoke(
            tool_name="github_list_issues",
            tool_input={"owner": "acme", "repo": "widgets"},
            access_token="gh-tok",
            http=http,
        )
    # GitHub's own API returns a bare array here — wrapped into a dict
    # envelope (matching every other connector's list-endpoint shape,
    # e.g. Jira's {"issues": [...]}) since invoke()'s own contract, and
    # InvokeResponse.output's schema, are both `dict`. A bare list here
    # previously passed pydantic validation right up until it reached
    # routers/invoke.py's real InvokeResponse(output=output) call in
    # production, which this connector-level test never exercised.
    assert result == {"issues": [{"number": 1}]}


async def test_github_invoke_unknown_tool_raises():
    connector = GitHubConnector()
    async with _mock_client(lambda r: httpx.Response(200)) as http:
        with pytest.raises(ConnectorError):
            await connector.invoke(
                tool_name="github_delete_repo", tool_input={}, access_token="tok", http=http
            )


# ---- Salesforce ---------------------------------------------------------


def test_salesforce_authorize_url_smoke():
    connector = SalesforceConnector()
    url = connector.authorize_url(state="s1", redirect_uri="https://x/cb")
    assert url.startswith("https://login.salesforce.com/services/oauth2/authorize")
    assert "state=s1" in url


async def test_salesforce_exchange_code_stores_instance_url():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "sf-tok",
                "refresh_token": "sf-refresh",
                "instance_url": "https://acme.my.salesforce.com",
                "id": "https://login.salesforce.com/id/00D/005",
            },
        )

    connector = SalesforceConnector()
    async with _mock_client(handler) as http:
        tokens = await connector.exchange_code(code="c1", redirect_uri="https://x/cb", http=http)

    assert tokens.extra == {"instance_url": "https://acme.my.salesforce.com"}
    assert tokens.expires_at is not None


async def test_salesforce_invoke_requires_instance_url():
    connector = SalesforceConnector()
    async with _mock_client(lambda r: httpx.Response(200)) as http:
        with pytest.raises(ConnectorError, match="reconnect required"):
            await connector.invoke(
                tool_name="salesforce_query",
                tool_input={"soql": "SELECT Id FROM Account"},
                access_token="tok",
                http=http,
                extra={},
            )


async def test_salesforce_invoke_query():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/services/data/v61.0/query"
        return httpx.Response(200, json={"records": []})

    connector = SalesforceConnector()
    async with _mock_client(handler) as http:
        result = await connector.invoke(
            tool_name="salesforce_query",
            tool_input={"soql": "SELECT Id FROM Account"},
            access_token="tok",
            http=http,
            extra={"instance_url": "https://acme.my.salesforce.com"},
        )
    assert result == {"records": []}


# ---- HubSpot --------------------------------------------------------------


def test_hubspot_authorize_url_smoke():
    connector = HubSpotConnector()
    url = connector.authorize_url(state="s1", redirect_uri="https://x/cb")
    assert url.startswith("https://app.hubspot.com/oauth/authorize")


async def test_hubspot_exchange_code_defaults_expiry_when_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "hs-tok", "refresh_token": "hs-refresh"})

    connector = HubSpotConnector()
    async with _mock_client(handler) as http:
        tokens = await connector.exchange_code(code="c1", redirect_uri="https://x/cb", http=http)

    assert tokens.access_token == "hs-tok"
    assert tokens.expires_at is not None


async def test_hubspot_invoke_create_contact():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content
        return httpx.Response(200, json={"id": "1"})

    connector = HubSpotConnector()
    async with _mock_client(handler) as http:
        result = await connector.invoke(
            tool_name="hubspot_create_contact",
            tool_input={"email": "a@example.com"},
            access_token="tok",
            http=http,
        )
    assert b"a@example.com" in seen["body"]
    assert result == {"id": "1"}


async def test_hubspot_invoke_raises_on_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "invalid input"})

    connector = HubSpotConnector()
    async with _mock_client(handler) as http:
        with pytest.raises(ConnectorError, match="invalid input"):
            await connector.invoke(
                tool_name="hubspot_search_contacts",
                tool_input={"query": "x"},
                access_token="tok",
                http=http,
            )


# ---- Microsoft Teams / 365 (shared OAuth mechanics) ------------------------


def test_teams_authorize_url_uses_common_endpoint():
    connector = MicrosoftTeamsConnector()
    url = connector.authorize_url(state="s1", redirect_uri="https://x/cb")
    assert url.startswith("https://login.microsoftonline.com/common/oauth2/v2.0/authorize")


async def test_teams_exchange_code_fetches_upn():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/common/oauth2/v2.0/token":
            return httpx.Response(200, json={"access_token": "ms-tok", "expires_in": 3600})
        if request.url.path == "/v1.0/me":
            return httpx.Response(200, json={"userPrincipalName": "employee@acme.com"})
        raise AssertionError(f"unexpected call to {request.url}")

    connector = MicrosoftTeamsConnector()
    async with _mock_client(handler) as http:
        tokens = await connector.exchange_code(code="c1", redirect_uri="https://x/cb", http=http)

    assert tokens.access_token == "ms-tok"
    assert tokens.external_account == "employee@acme.com"


async def test_teams_invoke_send_channel_message():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1.0/teams/T1/channels/C1/messages"
        return httpx.Response(200, json={"id": "msg1"})

    connector = MicrosoftTeamsConnector()
    async with _mock_client(handler) as http:
        result = await connector.invoke(
            tool_name="teams_send_channel_message",
            tool_input={"team_id": "T1", "channel_id": "C1", "text": "hi"},
            access_token="tok",
            http=http,
        )
    assert result == {"id": "msg1"}


def test_m365_authorize_url_uses_mail_scopes():
    connector = Microsoft365Connector()
    url = connector.authorize_url(state="s1", redirect_uri="https://x/cb")
    assert "Mail.Read" in url


async def test_m365_send_mail_handles_202_empty_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1.0/me/sendMail"
        return httpx.Response(202)

    connector = Microsoft365Connector()
    async with _mock_client(handler) as http:
        result = await connector.invoke(
            tool_name="m365_send_mail",
            tool_input={"to": "a@example.com", "subject": "Hi", "body": "Hello"},
            access_token="tok",
            http=http,
        )
    assert result == {"status": "sent"}


async def test_m365_invoke_raises_on_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="insufficient scope")

    connector = Microsoft365Connector()
    async with _mock_client(handler) as http:
        with pytest.raises(ConnectorError, match="insufficient scope"):
            await connector.invoke(
                tool_name="m365_list_mail", tool_input={}, access_token="tok", http=http
            )


# ---- ServiceNow -----------------------------------------------------------


def test_servicenow_authorize_url_requires_instance():
    connector = ServiceNowConnector()
    with pytest.raises(ConnectorError, match="instance name"):
        connector.authorize_url(state="s1", redirect_uri="https://x/cb", tenant_config=None)


def test_servicenow_authorize_url_builds_instance_subdomain():
    connector = ServiceNowConnector()
    url = connector.authorize_url(
        state="s1", redirect_uri="https://x/cb", tenant_config={"instance": "acme"}
    )
    assert url.startswith("https://acme.service-now.com/oauth_auth.do")


async def test_servicenow_exchange_code_stores_instance_in_extra():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "acme.service-now.com"
        return httpx.Response(200, json={"access_token": "sn-tok"})

    connector = ServiceNowConnector()
    async with _mock_client(handler) as http:
        tokens = await connector.exchange_code(
            code="c1", redirect_uri="https://x/cb", http=http, tenant_config={"instance": "acme"}
        )
    assert tokens.extra == {"instance": "acme"}


async def test_servicenow_invoke_requires_instance():
    connector = ServiceNowConnector()
    async with _mock_client(lambda r: httpx.Response(200)) as http:
        with pytest.raises(ConnectorError, match="reconnect required"):
            await connector.invoke(
                tool_name="servicenow_search_incidents",
                tool_input={},
                access_token="tok",
                http=http,
                extra={},
            )


async def test_servicenow_invoke_create_incident():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "acme.service-now.com"
        return httpx.Response(200, json={"result": {"sys_id": "abc"}})

    connector = ServiceNowConnector()
    async with _mock_client(handler) as http:
        result = await connector.invoke(
            tool_name="servicenow_create_incident",
            tool_input={"short_description": "printer down"},
            access_token="tok",
            http=http,
            extra={"instance": "acme"},
        )
    assert result == {"result": {"sys_id": "abc"}}


# ---- SAP --------------------------------------------------------------


def test_sap_authorize_url_requires_base_url():
    connector = SapConnector()
    with pytest.raises(ConnectorError, match="landscape base URL"):
        connector.authorize_url(state="s1", redirect_uri="https://x/cb", tenant_config=None)


def test_sap_authorize_url_smoke():
    connector = SapConnector()
    url = connector.authorize_url(
        state="s1",
        redirect_uri="https://x/cb",
        tenant_config={"sap_base_url": "https://my123456.s4hana.cloud.sap"},
    )
    assert url.startswith("https://my123456.s4hana.cloud.sap/sap/bc/sec/oauth2/authorize")


async def test_sap_exchange_code_stores_base_url_in_extra():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "sap-tok"})

    connector = SapConnector()
    async with _mock_client(handler) as http:
        tokens = await connector.exchange_code(
            code="c1",
            redirect_uri="https://x/cb",
            http=http,
            tenant_config={"sap_base_url": "https://my123456.s4hana.cloud.sap"},
        )
    assert tokens.extra == {"sap_base_url": "https://my123456.s4hana.cloud.sap"}


async def test_sap_invoke_requires_base_url():
    connector = SapConnector()
    async with _mock_client(lambda r: httpx.Response(200)) as http:
        with pytest.raises(ConnectorError, match="missing its base URL"):
            await connector.invoke(
                tool_name="sap_get_business_partners",
                tool_input={},
                access_token="tok",
                http=http,
                extra={},
            )


async def test_sap_invoke_get_business_partners():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "API_BUSINESS_PARTNER" in str(request.url)
        return httpx.Response(200, json={"d": {"results": []}})

    connector = SapConnector()
    async with _mock_client(handler) as http:
        result = await connector.invoke(
            tool_name="sap_get_business_partners",
            tool_input={},
            access_token="tok",
            http=http,
            extra={"sap_base_url": "https://my123456.s4hana.cloud.sap"},
        )
    assert result == {"d": {"results": []}}


# ---- Oracle -----------------------------------------------------------


def test_oracle_authorize_url_requires_base_url():
    connector = OracleConnector()
    with pytest.raises(ConnectorError, match="IDCS base URL"):
        connector.authorize_url(state="s1", redirect_uri="https://x/cb", tenant_config=None)


def test_oracle_authorize_url_smoke():
    connector = OracleConnector()
    url = connector.authorize_url(
        state="s1",
        redirect_uri="https://x/cb",
        tenant_config={"oracle_base_url": "https://idcs-xxxx.identity.oraclecloud.com"},
    )
    assert url.startswith("https://idcs-xxxx.identity.oraclecloud.com/oauth2/v1/authorize")


async def test_oracle_exchange_code_stores_both_base_urls():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"access_token": "oracle-tok", "refresh_token": "oracle-refresh"}
        )

    connector = OracleConnector()
    async with _mock_client(handler) as http:
        tokens = await connector.exchange_code(
            code="c1",
            redirect_uri="https://x/cb",
            http=http,
            tenant_config={
                "oracle_base_url": "https://idcs-xxxx.identity.oraclecloud.com",
                "oracle_fusion_base_url": "https://xxxx.fa.us2.oraclecloud.com",
            },
        )
    assert tokens.extra == {
        "oracle_base_url": "https://idcs-xxxx.identity.oraclecloud.com",
        "oracle_fusion_base_url": "https://xxxx.fa.us2.oraclecloud.com",
    }


async def test_oracle_invoke_requires_fusion_base_url():
    connector = OracleConnector()
    async with _mock_client(lambda r: httpx.Response(200)) as http:
        with pytest.raises(ConnectorError, match="reconnect required"):
            await connector.invoke(
                tool_name="oracle_get_suppliers",
                tool_input={},
                access_token="tok",
                http=http,
                extra={},
            )


async def test_oracle_invoke_get_suppliers():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/fscmRestApi/resources/" in str(request.url)
        return httpx.Response(200, json={"items": []})

    connector = OracleConnector()
    async with _mock_client(handler) as http:
        result = await connector.invoke(
            tool_name="oracle_get_suppliers",
            tool_input={},
            access_token="tok",
            http=http,
            extra={"oracle_fusion_base_url": "https://xxxx.fa.us2.oraclecloud.com"},
        )
    assert result == {"items": []}


# ---- WhatsApp -----------------------------------------------------------


def test_whatsapp_authorize_url_smoke():
    connector = WhatsAppConnector()
    url = connector.authorize_url(state="s1", redirect_uri="https://x/cb")
    assert url.startswith("https://www.facebook.com/v21.0/dialog/oauth")


async def test_whatsapp_exchange_code_requires_phone_number_id():
    connector = WhatsAppConnector()
    async with _mock_client(lambda r: httpx.Response(200)) as http:
        with pytest.raises(ConnectorError, match="phone_number_id"):
            await connector.exchange_code(
                code="c1", redirect_uri="https://x/cb", http=http, tenant_config=None
            )


async def test_whatsapp_exchange_code_stores_phone_number_id():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "wa-tok"})

    connector = WhatsAppConnector()
    async with _mock_client(handler) as http:
        tokens = await connector.exchange_code(
            code="c1",
            redirect_uri="https://x/cb",
            http=http,
            tenant_config={"phone_number_id": "1234567890"},
        )
    assert tokens.extra == {"phone_number_id": "1234567890"}
    assert tokens.refresh_token is None


async def test_whatsapp_invoke_requires_phone_number_id():
    connector = WhatsAppConnector()
    async with _mock_client(lambda r: httpx.Response(200)) as http:
        with pytest.raises(ConnectorError, match="reconnect required"):
            await connector.invoke(
                tool_name="whatsapp_send_message",
                tool_input={"to": "+15551234567", "text": "hi"},
                access_token="tok",
                http=http,
                extra={},
            )


async def test_whatsapp_invoke_send_message():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v21.0/1234567890/messages"
        return httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})

    connector = WhatsAppConnector()
    async with _mock_client(handler) as http:
        result = await connector.invoke(
            tool_name="whatsapp_send_message",
            tool_input={"to": "+15551234567", "text": "hi"},
            access_token="tok",
            http=http,
            extra={"phone_number_id": "1234567890"},
        )
    assert result == {"messages": [{"id": "wamid.1"}]}


async def test_whatsapp_invoke_unknown_tool_raises():
    connector = WhatsAppConnector()
    async with _mock_client(lambda r: httpx.Response(200)) as http:
        with pytest.raises(ConnectorError):
            await connector.invoke(
                tool_name="whatsapp_delete_account",
                tool_input={},
                access_token="tok",
                http=http,
                extra={"phone_number_id": "123"},
            )
