import logging
from collections.abc import Awaitable, Callable

import aio_pika

from .topics import EXCHANGE_NAME

logger = logging.getLogger(__name__)


async def consume(
    url: str,
    *,
    queue_name: str,
    routing_key: str,
    handler: Callable[[bytes], Awaitable[None]],
) -> None:
    """Connects, declares the shared exchange and this consumer's own
    queue bound to routing_key, and processes messages until the
    connection is closed or the task is cancelled.

    A message that makes `handler` raise is logged and dropped (acked),
    not redelivered forever — there's no dead-letter queue yet, so an
    unbounded retry loop on a truly poison message would just wedge this
    queue; that's the natural next step if that ever becomes a real
    problem, not needed for a walking skeleton.
    """
    connection = await aio_pika.connect_robust(url)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await channel.declare_queue(queue_name, durable=True)
        await queue.bind(exchange, routing_key=routing_key)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process(ignore_processed=True):
                    try:
                        await handler(message.body)
                    except Exception:
                        logger.exception(
                            "failed to process message on queue %r (routing_key=%r) — dropping",
                            queue_name,
                            routing_key,
                        )
