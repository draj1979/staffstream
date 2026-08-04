import time
from typing import Protocol


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"rate limit exceeded, retry after {retry_after}s")


class RedisLike(Protocol):
    async def incr(self, key: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> object: ...
    async def ttl(self, key: str) -> int: ...


class RateLimiter:
    """Fixed-window counter in Redis, keyed per-tenant (see identity.py) —
    shared across every gateway replica, unlike an in-process counter,
    which is what actually matters once this runs as more than one pod."""

    def __init__(self, redis_client: RedisLike, *, max_requests: int, window_seconds: int):
        self._redis = redis_client
        self._max_requests = max_requests
        self._window_seconds = window_seconds

    async def check(self, bucket_key: str) -> None:
        window = int(time.time()) // self._window_seconds
        key = f"ratelimit:{bucket_key}:{window}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, self._window_seconds)
        if count > self._max_requests:
            ttl = await self._redis.ttl(key)
            raise RateLimitExceeded(retry_after=max(ttl, 1))
