from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="KNOWLEDGE_SERVICE_", extra="ignore", populate_by_name=True
    )

    database_url: str = (
        "postgresql+asyncpg://staffstream:staffstream@localhost:5434/knowledge_service"
    )
    chunk_size: int = 1000
    chunk_overlap: int = 200
    default_top_k: int = 5

    # Deliberately unprefixed (alias bypasses env_prefix): VOYAGE_API_KEY
    # is the standard env var name the Voyage AI SDK itself looks for.
    # Local-dev placeholder only — real deployments set this from
    # Vault / Secret Manager. A real call with this value fails with a
    # normal auth error from Voyage; it doesn't crash the service at startup.
    voyage_api_key: str = Field(default="not-set-configure-VOYAGE_API_KEY", alias="VOYAGE_API_KEY")


settings = Settings()
