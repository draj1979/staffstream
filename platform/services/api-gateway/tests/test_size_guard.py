import pytest
from api_gateway.proxy import _read_body_with_limit
from fastapi import HTTPException


class FakeRequestWithLyingContentLength:
    """A request whose Content-Length header understates the real body —
    the streaming guard, not the header pre-check, is what has to catch
    this."""

    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks

    async def stream(self):
        for chunk in self._chunks:
            yield chunk


async def test_streaming_guard_rejects_body_exceeding_limit_regardless_of_header():
    request = FakeRequestWithLyingContentLength([b"x" * 10, b"y" * 10, b"z" * 10])

    with pytest.raises(HTTPException) as exc_info:
        await _read_body_with_limit(request, limit=15)

    assert exc_info.value.status_code == 413


async def test_streaming_guard_allows_body_within_limit():
    request = FakeRequestWithLyingContentLength([b"x" * 10, b"y" * 10])

    body = await _read_body_with_limit(request, limit=100)

    assert body == b"x" * 10 + b"y" * 10
