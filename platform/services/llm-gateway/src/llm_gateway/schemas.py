from pydantic import Field

from .config import settings
from .models import LLMRequest


class GenerateRequest(LLMRequest):
    provider: str = Field(default_factory=lambda: settings.default_provider)
