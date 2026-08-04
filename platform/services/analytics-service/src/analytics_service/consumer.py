"""Starts the two background consumer tasks (one per event type) that
ingest from RabbitMQ for as long as the process runs. Started from
main.py's lifespan, not tied to any single HTTP request."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from events import (
    QUEUE_CHAT_INTERACTION,
    QUEUE_LLM_USAGE,
    ROUTING_KEY_CHAT_INTERACTION,
    ROUTING_KEY_LLM_USAGE,
    consume,
)

from .config import settings
from .ingestion import handle_chat_interaction_event, handle_llm_usage_event

logger = logging.getLogger(__name__)


async def _run_forever(name: str, run_once: Callable[[], Awaitable[None]]) -> None:
    """Reconnects with exponential backoff if the broker connection drops
    — a consumer task silently dying would mean analytics just stops
    ingesting with no visible signal, which is worse than a log line
    every so often while the broker is unreachable."""
    delay = 1.0
    while True:
        try:
            await run_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("%s consumer crashed, reconnecting in %.1fs", name, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)
        else:
            delay = 1.0


def start_consumers() -> list[asyncio.Task]:
    return [
        asyncio.create_task(
            _run_forever(
                "llm_usage",
                lambda: consume(
                    settings.rabbitmq_url,
                    queue_name=QUEUE_LLM_USAGE,
                    routing_key=ROUTING_KEY_LLM_USAGE,
                    handler=handle_llm_usage_event,
                ),
            )
        ),
        asyncio.create_task(
            _run_forever(
                "chat_interaction",
                lambda: consume(
                    settings.rabbitmq_url,
                    queue_name=QUEUE_CHAT_INTERACTION,
                    routing_key=ROUTING_KEY_CHAT_INTERACTION,
                    handler=handle_chat_interaction_event,
                ),
            )
        ),
    ]


async def stop_consumers(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
