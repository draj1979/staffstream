from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="AUTH_SERVICE_", extra="ignore", populate_by_name=True
    )

    database_url: str = "postgresql+asyncpg://staffstream:staffstream@localhost:5432/auth_service"
    employee_service_url: str = "http://localhost:8002"

    # Shared infra, deliberately unprefixed (alias bypasses env_prefix) —
    # same broker every service that publishes/consumes analytics/audit
    # events would use.
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL")

    # Fernet key (32 url-safe base64 bytes) used to encrypt each tenant's
    # SSO client secret at rest — see crypto.py. Local-dev placeholder
    # only; real deployments must set this from Vault / Secret Manager,
    # same as JWT_SECRET_KEY. Generate one with `Fernet.generate_key()`.
    sso_encryption_key: str = Field(
        default="gglttmY9baFzyNjGySfCNv-Xg_r-vaxIePrRyNv-s9Q=",
        alias="SSO_ENCRYPTION_KEY",
    )

    # Base URL this service is externally reachable at — used to build
    # the OIDC redirect_uri (must match what's registered with each
    # tenant's IdP exactly, protocol and path included).
    public_base_url: str = "http://localhost:8003"


settings = Settings()
