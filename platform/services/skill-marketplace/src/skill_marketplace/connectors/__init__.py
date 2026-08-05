from .base import Connector, ConnectorError, TokenSet, ToolSpec
from .github import GitHubConnector
from .google_calendar import GoogleCalendarConnector
from .hubspot import HubSpotConnector
from .jira import JiraConnector
from .microsoft_365 import Microsoft365Connector
from .microsoft_teams import MicrosoftTeamsConnector
from .oracle import OracleConnector
from .salesforce import SalesforceConnector
from .sap import SapConnector
from .servicenow import ServiceNowConnector
from .slack import SlackConnector
from .whatsapp import WhatsAppConnector

# The one place a new connector gets wired in — everything else (routers,
# crud, OpenClaw's tool loading) looks skills up through this registry by
# skill_id, never imports a connector class directly.
CONNECTOR_REGISTRY: dict[str, Connector] = {
    "slack": SlackConnector(),
    "google_calendar": GoogleCalendarConnector(),
    "salesforce": SalesforceConnector(),
    "hubspot": HubSpotConnector(),
    "jira": JiraConnector(),
    "github": GitHubConnector(),
    "microsoft_teams": MicrosoftTeamsConnector(),
    "microsoft_365": Microsoft365Connector(),
    "servicenow": ServiceNowConnector(),
    "sap": SapConnector(),
    "oracle": OracleConnector(),
    "whatsapp": WhatsAppConnector(),
}

__all__ = [
    "Connector",
    "ConnectorError",
    "ToolSpec",
    "TokenSet",
    "GoogleCalendarConnector",
    "SlackConnector",
    "SalesforceConnector",
    "HubSpotConnector",
    "JiraConnector",
    "GitHubConnector",
    "MicrosoftTeamsConnector",
    "Microsoft365Connector",
    "ServiceNowConnector",
    "SapConnector",
    "OracleConnector",
    "WhatsAppConnector",
    "CONNECTOR_REGISTRY",
]
