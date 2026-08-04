import asyncio
import os
import uuid

from events.topics import ROUTING_KEY_LLM_USAGE

from events import (
    LLMUsageEvent,
    RabbitMQPublisher,
    consume,
)

RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")


async def test_publish_and_consume_round_trip(rabbitmq_available):
    received: list[bytes] = []
    queue_name = f"test.llm_usage.{uuid.uuid4().hex}"

    async def handler(body: bytes) -> None:
        received.append(body)

    consumer_task = asyncio.create_task(
        consume(
            RABBITMQ_URL,
            queue_name=queue_name,
            routing_key=ROUTING_KEY_LLM_USAGE,
            handler=handler,
        )
    )
    await asyncio.sleep(0.5)  # let the consumer finish declaring/binding the queue

    publisher = RabbitMQPublisher(RABBITMQ_URL)
    event = LLMUsageEvent(
        tenant_id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        provider="claude",
        model="claude-sonnet-5",
        input_tokens=100,
        output_tokens=20,
        cost_usd=0.002,
    )
    try:
        await publisher.publish(ROUTING_KEY_LLM_USAGE, event.model_dump_json().encode())

        for _ in range(20):
            if received:
                break
            await asyncio.sleep(0.25)
    finally:
        await publisher.close()
        consumer_task.cancel()
        try:
            await consumer_task
        except (asyncio.CancelledError, Exception):
            pass

    assert len(received) == 1
    assert LLMUsageEvent.model_validate_json(received[0]) == event


async def test_bad_message_is_dropped_not_requeued_forever(rabbitmq_available):
    """A message the handler can't process gets logged and acked — not
    redelivered in an infinite loop."""
    processed_count = 0
    queue_name = f"test.poison.{uuid.uuid4().hex}"

    async def handler(body: bytes) -> None:
        nonlocal processed_count
        processed_count += 1
        raise ValueError("simulated bad message")

    consumer_task = asyncio.create_task(
        consume(
            RABBITMQ_URL,
            queue_name=queue_name,
            routing_key=ROUTING_KEY_LLM_USAGE,
            handler=handler,
        )
    )
    await asyncio.sleep(0.5)

    publisher = RabbitMQPublisher(RABBITMQ_URL)
    try:
        await publisher.publish(ROUTING_KEY_LLM_USAGE, b"not valid json at all")
        await asyncio.sleep(1.5)  # give it time to redeliver if it were going to
    finally:
        await publisher.close()
        consumer_task.cancel()
        try:
            await consumer_task
        except (asyncio.CancelledError, Exception):
            pass

    # Processed exactly once — no redelivery loop.
    assert processed_count == 1
