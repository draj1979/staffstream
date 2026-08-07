"""The contract every connector implements. Each connector owns its own
OAuth dance (authorize URL, code exchange, optional refresh) and its own
tool implementations — nothing in the rest of the service knows Slack,
Google's, Salesforce's, ... API shapes; it only knows this interface.

Every `invoke`/`exchange_code`/`refresh` call receives the httpx client to
use rather than constructing its own, so tests can swap in a
`httpx.MockTransport` without any connector code caring.

Two extension points Phase 10 adds, needed by the enterprise connectors
but not by Slack/Google Calendar (which both ignore them):

- `tenant_config` (TenantSkillEnablement.config, already existed since
  Phase 8) carries whatever per-tenant instance info a connector needs
  before an employee can even start the OAuth flow — e.g. ServiceNow's
  and SAP's OAuth endpoints are per-instance, not one fixed global URL
  the way Slack's or GitHub's are. An admin sets this once via the
  existing `PUT /skills/{id}/enablement` (its `config` field), the same
  place enablement itself is already set — not a new admin surface.
- `TokenSet.extra` / `invoke`'s `extra` param carry whatever the OAuth
  exchange itself hands back that a connector needs to make later calls
  — Salesforce's `instance_url`, Jira's `cloudId` — persisted alongside
  the encrypted tokens (EmployeeConnection.connection_metadata) and
  handed back on every invoke.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import httpx


class ConnectorError(Exception):
    """Raised when the upstream provider (Slack/Google/Salesforce/...)
    rejects a call — bad/expired token, insufficient scope, unknown tool,
    rate limit."""


def has_real_value(value: str | None) -> bool:
    """True if a Settings field holds an actual configured value, as
    opposed to being unset entirely or left as the `"not-set"`/
    `"not-set-configure-X"` placeholder every `*_client_id` in config.py
    defaults to. Deliberately also rejects the empty string: an env var
    that's declared but assigned nothing (e.g. `GITHUB_CLIENT_ID=` in a
    docker-compose env file whose GitHub Actions secret was never set)
    overrides pydantic-settings' own "not-set" default with `""` — which
    passed a naive `.startswith("not-set")` check, since `"".startswith(...)`
    is `False`, and silently let every one of the 12 connectors think it
    was configured when none of them were. Every connector's
    `is_configured()` must go through this, not repeat the check inline."""
    return bool(value) and not value.startswith("not-set")


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scope: str | None
    external_account: str | None  # display-only identity at the provider
    extra: dict = field(default_factory=dict)


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict


class Connector(ABC):
    skill_id: str
    supports_refresh: bool = False

    def is_configured(self) -> bool:
        """Whether this connector's own OAuth app credentials have
        actually been set to something real, as opposed to the
        `"not-set"`/`"not-set-configure-X"` placeholder every
        `*_client_id`/`*_client_secret` in config.py defaults to.
        Checked by routers/connections.py's `/authorize` route *before*
        redirecting the employee anywhere — without this, an unconfigured
        connector still 307s straight to the real provider with a
        placeholder client_id, and the employee lands on THAT provider's
        own raw "invalid_client" error page instead of ever coming back
        to this app. Default True (assume configured) since not every
        connector necessarily gets its credentials from Settings the
        same way; override wherever they do — every connector currently
        shipped does, one line each, e.g. google_calendar.py's."""
        return True

    @abstractmethod
    def tool_specs(self) -> list[ToolSpec]:
        """The tools this connector exposes to the LLM, in the shared
        {name, description, input_schema} shape OpenClaw Runtime turns
        into an Anthropic ToolDefinition."""

    @abstractmethod
    def authorize_url(
        self, *, state: str, redirect_uri: str, tenant_config: dict | None = None
    ) -> str: ...

    @abstractmethod
    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        http: httpx.AsyncClient,
        tenant_config: dict | None = None,
    ) -> TokenSet: ...

    async def refresh(
        self, *, refresh_token: str, http: httpx.AsyncClient, tenant_config: dict | None = None
    ) -> TokenSet:
        raise NotImplementedError(f"{self.skill_id} does not support token refresh")

    @abstractmethod
    async def invoke(
        self,
        *,
        tool_name: str,
        tool_input: dict,
        access_token: str,
        http: httpx.AsyncClient,
        extra: dict | None = None,
    ) -> dict:
        """Execute one tool call using the employee's own access token —
        the token is the entire authorization boundary; there is no
        broader tenant- or service-level credential a connector could
        reach for instead."""
