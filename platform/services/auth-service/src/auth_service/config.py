from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AUTH_SERVICE_", extra="ignore")

    database_url: str = "postgresql+asyncpg://staffstream:staffstream@localhost:5432/auth_service"
    employee_service_url: str = "http://localhost:8002"


settings = Settings()
