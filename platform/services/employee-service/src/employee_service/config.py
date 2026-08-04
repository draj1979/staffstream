from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="EMPLOYEE_SERVICE_", extra="ignore"
    )

    database_url: str = (
        "postgresql+asyncpg://staffstream:staffstream@localhost:5432/employee_service"
    )
    agent_registry_url: str = "http://localhost:8004"


settings = Settings()
