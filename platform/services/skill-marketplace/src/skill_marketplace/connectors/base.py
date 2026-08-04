"""The contract every connector implements. Each connector owns its own
OAuth dance (authorize URL, code exchange, optional refresh) and its own
tool implementations — nothing in the rest of the service knows Slack or
Google's API shapes; it only knows this interface.

Every `invoke`/`exchange_code`/`refresh` call receives the httpx client to
use rather than constructing its own, so tests can swap in a
`httpx.MockTransport` without any connector code caring.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import httpx


class ConnectorError(Exception):
    """Raised when the upstream provider (Slack/Google/...) rejects a call
    — bad/expired token, insufficient scope, unknown tool, rate limit."""


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scope: str | None
    external_account: str | None  # display-only identity at the provider


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict


class Connector(ABC):
    skill_id: str
    supports_refresh: bool = False

    @abstractmethod
    def tool_specs(self) -> list[ToolSpec]:
        """The tools this connector exposes to the LLM, in the shared
        {name, description, input_schema} shape OpenClaw Runtime turns
        into an Anthropic ToolDefinition."""

    @abstractmethod
    def authorize_url(self, *, state: str, redirect_uri: str) -> str: ...

    @abstractmethod
    async def exchange_code(
        self, *, code: str, redirect_uri: str, http: httpx.AsyncClient
    ) -> TokenSet: ...

    async def refresh(self, *, refresh_token: str, http: httpx.AsyncClient) -> TokenSet:
        raise NotImplementedError(f"{self.skill_id} does not support token refresh")

    @abstractmethod
    async def invoke(
        self, *, tool_name: str, tool_input: dict, access_token: str, http: httpx.AsyncClient
    ) -> dict:
        """Execute one tool call using the employee's own access token —
        the token is the entire authorization boundary; there is no
        broader tenant- or service-level credential a connector could
        reach for instead."""
