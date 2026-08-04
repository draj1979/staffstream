from abc import ABC, abstractmethod

import aio_pika

from .topics import EXCHANGE_NAME


class Publisher(ABC):
    @abstractmethod
    async def publish(self, routing_key: str, payload: bytes) -> None: ...

    async def close(self) -> None:
        """Override if the implementation holds a connection to release."""
        return None


class RabbitMQPublisher(Publisher):
    """Connects lazily on first publish and reuses the connection/channel
    after that. Declares the shared topic exchange idempotently, so
    publishing works whether or not Analytics Service (the consumer) has
    started yet — standard pub/sub decoupling, not a direct dependency."""

    def __init__(self, url: str):
        self._url = url
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def _ensure_connected(self) -> aio_pika.abc.AbstractExchange:
        if self._exchange is not None:
            return self._exchange
        self._connection = await aio_pika.connect_robust(self._url)
        channel = await self._connection.channel()
        self._exchange = await channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        return self._exchange

    async def publish(self, routing_key: str, payload: bytes) -> None:
        exchange = await self._ensure_connected()
        await exchange.publish(
            aio_pika.Message(
                body=payload,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
