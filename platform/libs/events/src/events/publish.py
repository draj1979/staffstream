"""Fire-and-forget publish helper — the same pattern LLM Gateway and
OpenClaw Runtime each hand-wrote for their own event types (Phase 7/8):
schedule with asyncio.create_task, never await it from the request path,
keep a strong reference on app.state until it finishes (create_task's
well-known garbage-collection gotcha), and swallow any publish failure so
a broker hiccup never surfaces as a request-facing error. Pulled out here
once a fourth call site (audit events, Phase 9) needed the exact same
dozen lines — existing call sites aren't required to switch to it.
"""

import asyncio
import logging
from typing import Protocol

from .publisher import Publisher

logger = logging.getLogger(__name__)


class _HasBackgroundTasks(Protocol):
    background_tasks: set[asyncio.Task]


async def _publish_and_log_failure(publisher: Publisher, routing_key: str, payload: bytes) -> None:
    try:
        await publisher.publish(routing_key, payload)
    except Exception:
        logger.exception("failed to publish event to routing key %r", routing_key)


def schedule_publish(
    app_state: _HasBackgroundTasks, publisher: Publisher, routing_key: str, payload: bytes
) -> None:
    task = asyncio.create_task(_publish_and_log_failure(publisher, routing_key, payload))
    app_state.background_tasks.add(task)
    task.add_done_callback(app_state.background_tasks.discard)
