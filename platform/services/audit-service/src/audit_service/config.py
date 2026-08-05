from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="AUDIT_SERVICE_", extra="ignore", populate_by_name=True
    )

    database_url: str = (
        "postgresql+asyncpg://staffstream:staffstream@localhost:5433/audit_service"
    )
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL")


settings = Settings()
