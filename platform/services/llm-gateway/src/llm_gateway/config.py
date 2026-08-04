from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Deliberately unprefixed: ANTHROPIC_API_KEY is the standard env var
    # name the Anthropic SDK itself looks for. Local-dev placeholder only —
    # real deployments set this from Vault / Secret Manager. A real call
    # with this value fails with a normal 401 from Anthropic; it doesn't
    # crash the service at startup.
    anthropic_api_key: str = "not-set-configure-ANTHROPIC_API_KEY"
    default_provider: str = "claude"

    # Shared infra, deliberately unprefixed — same broker every service
    # that publishes/consumes analytics events would use.
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"


settings = Settings()
