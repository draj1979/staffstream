from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="OPENCLAW_RUNTIME_", extra="ignore", populate_by_name=True
    )

    agent_registry_url: str = "http://localhost:8004"
    llm_gateway_url: str = "http://localhost:8005"
    memory_service_url: str = "http://localhost:8007"
    employee_service_url: str = "http://localhost:8002"
    knowledge_service_url: str = "http://localhost:8008"

    # Shared infra, deliberately unprefixed (alias bypasses env_prefix) —
    # same broker every service that publishes/consumes analytics events
    # would use.
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL")


settings = Settings()
