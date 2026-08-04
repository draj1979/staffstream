from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MEMORY_SERVICE_", extra="ignore")

    database_url: str = (
        "postgresql+asyncpg://staffstream:staffstream@localhost:5432/memory_service"
    )


settings = Settings()
