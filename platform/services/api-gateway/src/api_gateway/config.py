from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Shared infra, deliberately unprefixed — same Redis every service would use.
    redis_url: str = Field("redis://localhost:6379/0", validation_alias="REDIS_URL")

    rate_limit_max_requests: int = Field(
        120, validation_alias="API_GATEWAY_RATE_LIMIT_MAX_REQUESTS"
    )
    rate_limit_window_seconds: int = Field(
        60, validation_alias="API_GATEWAY_RATE_LIMIT_WINDOW_SECONDS"
    )

    # Content-Length pre-check + hard streaming guard. Uploads (knowledge
    # service's /documents) get a much higher ceiling than everything else.
    max_body_bytes: int = Field(2 * 1024 * 1024, validation_alias="API_GATEWAY_MAX_BODY_BYTES")
    max_upload_body_bytes: int = Field(
        25 * 1024 * 1024, validation_alias="API_GATEWAY_MAX_UPLOAD_BODY_BYTES"
    )

    upstream_timeout_seconds: float = Field(
        30.0, validation_alias="API_GATEWAY_UPSTREAM_TIMEOUT_SECONDS"
    )

    tenant_service_url: str = Field(
        "http://localhost:8001", validation_alias="API_GATEWAY_TENANT_SERVICE_URL"
    )
    employee_service_url: str = Field(
        "http://localhost:8002", validation_alias="API_GATEWAY_EMPLOYEE_SERVICE_URL"
    )
    auth_service_url: str = Field(
        "http://localhost:8003", validation_alias="API_GATEWAY_AUTH_SERVICE_URL"
    )
    agent_registry_url: str = Field(
        "http://localhost:8004", validation_alias="API_GATEWAY_AGENT_REGISTRY_URL"
    )
    llm_gateway_url: str = Field(
        "http://localhost:8005", validation_alias="API_GATEWAY_LLM_GATEWAY_URL"
    )
    openclaw_runtime_url: str = Field(
        "http://localhost:8006", validation_alias="API_GATEWAY_OPENCLAW_RUNTIME_URL"
    )
    memory_service_url: str = Field(
        "http://localhost:8007", validation_alias="API_GATEWAY_MEMORY_SERVICE_URL"
    )
    knowledge_service_url: str = Field(
        "http://localhost:8008", validation_alias="API_GATEWAY_KNOWLEDGE_SERVICE_URL"
    )
    skill_marketplace_url: str = Field(
        "http://localhost:8010", validation_alias="API_GATEWAY_SKILL_MARKETPLACE_URL"
    )


settings = Settings()
