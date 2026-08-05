"""Starts the background consumer task that ingests audit events from
RabbitMQ for as long as the process runs. Started from main.py's
lifespan, not tied to any single HTTP request."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from events import QUEUE_AUDIT, ROUTING_KEY_AUDIT, consume

from .config import settings
from .ingestion import handle_audit_event

logger = logging.getLogger(__name__)


async def _run_forever(name: str, run_once: Callable[[], Awaitable[None]]) -> None:
    """Reconnects with exponential backoff if the broker connection drops
    — a consumer task silently dying would mean the audit trail just
    stops recording with no visible signal, which is worse than a log
    line every so often while the broker is unreachable."""
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
                "audit",
                lambda: consume(
                    settings.rabbitmq_url,
                    queue_name=QUEUE_AUDIT,
                    routing_key=ROUTING_KEY_AUDIT,
                    handler=handle_audit_event,
                ),
            )
        )
    ]


async def stop_consumers(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
