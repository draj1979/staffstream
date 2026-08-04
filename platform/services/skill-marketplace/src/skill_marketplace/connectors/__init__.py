from .base import Connector, ConnectorError, TokenSet, ToolSpec
from .google_calendar import GoogleCalendarConnector
from .slack import SlackConnector

# The one place a new connector gets wired in — everything else (routers,
# crud, OpenClaw's tool loading) looks skills up through this registry by
# skill_id, never imports a connector class directly.
CONNECTOR_REGISTRY: dict[str, Connector] = {
    "slack": SlackConnector(),
    "google_calendar": GoogleCalendarConnector(),
}

__all__ = [
    "Connector",
    "ConnectorError",
    "ToolSpec",
    "TokenSet",
    "GoogleCalendarConnector",
    "SlackConnector",
    "CONNECTOR_REGISTRY",
]
