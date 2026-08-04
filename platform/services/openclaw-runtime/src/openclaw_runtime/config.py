from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="OPENCLAW_RUNTIME_", extra="ignore"
    )

    agent_registry_url: str = "http://localhost:8004"
    llm_gateway_url: str = "http://localhost:8005"
    memory_service_url: str = "http://localhost:8007"
    employee_service_url: str = "http://localhost:8002"
    knowledge_service_url: str = "http://localhost:8008"


settings = Settings()
