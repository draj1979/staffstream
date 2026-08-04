from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="ANALYTICS_SERVICE_", extra="ignore", populate_by_name=True
    )

    database_url: str = (
        "postgresql+asyncpg://staffstream:staffstream@localhost:5432/analytics_service"
    )

    # Shared infra, deliberately unprefixed (alias bypasses env_prefix) —
    # same broker every service that publishes/consumes analytics events
    # would use.
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL")


settings = Settings()
