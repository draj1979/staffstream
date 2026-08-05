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

    # Phase 10 — five more providers, all sharing OpenAICompatibleProvider
    # (see providers/openai_compatible.py) except Claude. Each api_key is
    # deliberately unprefixed, matching whatever env var name that
    # provider's own SDK/tooling conventionally looks for; base_urls have
    # working defaults (each vendor's real endpoint, or — for Llama, which
    # has no single canonical hosted API — Groq's OpenAI-compatible one)
    # but are overridable for a self-hosted or alternate-vendor setup.
    openai_api_key: str = "not-set-configure-OPENAI_API_KEY"
    openai_base_url: str = "https://api.openai.com/v1"

    gemini_api_key: str = "not-set-configure-GEMINI_API_KEY"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"

    mistral_api_key: str = "not-set-configure-MISTRAL_API_KEY"
    mistral_base_url: str = "https://api.mistral.ai/v1"

    deepseek_api_key: str = "not-set-configure-DEEPSEEK_API_KEY"
    deepseek_base_url: str = "https://api.deepseek.com"

    llama_api_key: str = "not-set-configure-LLAMA_API_KEY"
    llama_base_url: str = "https://api.groq.com/openai/v1"

    # Shared infra, deliberately unprefixed — same broker every service
    # that publishes/consumes analytics events would use.
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"


settings = Settings()
