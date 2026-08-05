from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="SKILL_MARKETPLACE_", extra="ignore", populate_by_name=True
    )

    database_url: str = (
        "postgresql+asyncpg://staffstream:staffstream@localhost:5433/skill_marketplace"
    )

    # Fernet key (32 url-safe base64 bytes) used to encrypt OAuth tokens at
    # rest — see crypto.py. Local-dev placeholder only; real deployments
    # must set this from Vault / Secret Manager, same as JWT_SECRET_KEY.
    # Generate one with `Fernet.generate_key()`.
    oauth_encryption_key: str = Field(
        default="lhp4HtY3bSUeh04zFJhS63DBmXPeAgB-TKRD2pOeWoc=",
        alias="OAUTH_ENCRYPTION_KEY",
    )

    # Base URL this service is externally reachable at — used to build
    # each connector's OAuth redirect_uri (must match what's registered
    # with Slack/Google exactly, protocol and path included).
    public_base_url: str = "http://localhost:8010"

    # Slack OAuth v2 app credentials — deliberately unprefixed (alias
    # bypasses env_prefix), same reasoning as ANTHROPIC_API_KEY/
    # VOYAGE_API_KEY elsewhere: these are the standard names a Slack app
    # registration gives you. Placeholders until a real app is registered
    # — without them the Slack connector's authorize/exchange calls fail
    # with a normal 401/400 from Slack; the service still starts.
    slack_client_id: str = Field(
        default="not-set-configure-SLACK_CLIENT_ID", alias="SLACK_CLIENT_ID"
    )
    slack_client_secret: str = Field(
        default="not-set-configure-SLACK_CLIENT_SECRET", alias="SLACK_CLIENT_SECRET"
    )

    # Google OAuth2 app credentials — same placeholder + unprefixed story.
    google_client_id: str = Field(
        default="not-set-configure-GOOGLE_CLIENT_ID", alias="GOOGLE_CLIENT_ID"
    )
    google_client_secret: str = Field(
        default="not-set-configure-GOOGLE_CLIENT_SECRET", alias="GOOGLE_CLIENT_SECRET"
    )

    # Phase 10 — ten more connectors, same placeholder + unprefixed story
    # as Slack/Google above: each app is registered once at the platform
    # level (one Salesforce Connected App, one GitHub OAuth App, ...);
    # per-tenant instance details that DO vary (ServiceNow's instance
    # subdomain, SAP's/Oracle's tenant base URL) live in
    # TenantSkillEnablement.config instead, set via the existing
    # PUT /skills/{id}/enablement — not another env var per tenant.
    salesforce_client_id: str = Field(default="not-set", alias="SALESFORCE_CLIENT_ID")
    salesforce_client_secret: str = Field(default="not-set", alias="SALESFORCE_CLIENT_SECRET")

    hubspot_client_id: str = Field(default="not-set", alias="HUBSPOT_CLIENT_ID")
    hubspot_client_secret: str = Field(default="not-set", alias="HUBSPOT_CLIENT_SECRET")

    jira_client_id: str = Field(default="not-set", alias="JIRA_CLIENT_ID")
    jira_client_secret: str = Field(default="not-set", alias="JIRA_CLIENT_SECRET")

    github_client_id: str = Field(default="not-set", alias="GITHUB_CLIENT_ID")
    github_client_secret: str = Field(default="not-set", alias="GITHUB_CLIENT_SECRET")

    # Shared by Microsoft Teams and Microsoft 365 — both go through the
    # same Microsoft Entra ID (Azure AD) app registration and Graph API.
    microsoft_client_id: str = Field(default="not-set", alias="MICROSOFT_CLIENT_ID")
    microsoft_client_secret: str = Field(default="not-set", alias="MICROSOFT_CLIENT_SECRET")

    servicenow_client_id: str = Field(default="not-set", alias="SERVICENOW_CLIENT_ID")
    servicenow_client_secret: str = Field(default="not-set", alias="SERVICENOW_CLIENT_SECRET")

    sap_client_id: str = Field(default="not-set", alias="SAP_CLIENT_ID")
    sap_client_secret: str = Field(default="not-set", alias="SAP_CLIENT_SECRET")

    oracle_client_id: str = Field(default="not-set", alias="ORACLE_CLIENT_ID")
    oracle_client_secret: str = Field(default="not-set", alias="ORACLE_CLIENT_SECRET")

    whatsapp_client_id: str = Field(default="not-set", alias="WHATSAPP_CLIENT_ID")
    whatsapp_client_secret: str = Field(default="not-set", alias="WHATSAPP_CLIENT_SECRET")

    # Shared infra, deliberately unprefixed (alias bypasses env_prefix) —
    # same broker every service that publishes/consumes analytics/audit
    # events would use.
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL")


settings = Settings()
