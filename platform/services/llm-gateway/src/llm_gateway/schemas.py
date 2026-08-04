import uuid

from pydantic import Field

from .config import settings
from .models import LLMRequest


class GenerateRequest(LLMRequest):
    provider: str = Field(default_factory=lambda: settings.default_provider)
    # Which agent is making this call, purely for analytics attribution
    # (skill usage / agent health dashboards) — OpenClaw Runtime is the
    # only caller that currently supplies it. Optional so nothing else
    # calling /generate directly has to know or care.
    agent_id: uuid.UUID | None = None
