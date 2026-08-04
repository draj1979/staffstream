import os

import aio_pika
import pytest

RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")


@pytest.fixture
async def rabbitmq_available():
    """RabbitMQ is real infra, not something to fake for a pub/sub
    round-trip test — skip cleanly (not a failure) when none is reachable,
    same pattern as knowledge-service's Postgres+pgvector tests."""
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL, timeout=3)
        await connection.close()
    except Exception as exc:
        pytest.skip(f"RabbitMQ not reachable at {RABBITMQ_URL}: {exc}")
    return True
