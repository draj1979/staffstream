import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from .dependencies import get_http_client, get_rate_limiter
from .identity import resolve_bucket_key
from .rate_limit import RateLimiter, RateLimitExceeded
from .routing import max_body_bytes_for_path, resolve_upstream

logger = logging.getLogger(__name__)

router = APIRouter()

# Headers that are specific to a single hop and must never be blindly
# relayed to the other side of the proxy (both directions).
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def _forward_headers(headers) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP_HEADERS}


async def _read_body_with_limit(request: Request, limit: int) -> bytes:
    """Content-Length is checked before this runs, but a client can lie
    about it — this is the real, un-spoofable enforcement, counting bytes
    as they actually arrive."""
    chunks = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Request body too large",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
)
async def proxy(
    path: str,
    request: Request,
    http_client: httpx.AsyncClient = Depends(get_http_client),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    upstream_base = resolve_upstream(path)
    if upstream_base is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No route for this path")

    limit = max_body_bytes_for_path(path)
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > limit:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Request body too large",
                )
        except ValueError:
            pass  # malformed header — the streaming guard below still enforces the real limit

    bucket_key = resolve_bucket_key(request)
    try:
        await rate_limiter.check(bucket_key)
    except RateLimitExceeded as exc:
        return JSONResponse(
            {"detail": "Too many requests"},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(exc.retry_after)},
        )

    body = await _read_body_with_limit(request, limit)

    upstream_url = f"{upstream_base.rstrip('/')}/{path}"
    try:
        upstream_response = await http_client.request(
            request.method,
            upstream_url,
            params=list(request.query_params.multi_items()),
            content=body,
            headers=_forward_headers(request.headers),
        )
    except httpx.RequestError as exc:
        logger.error("upstream unreachable: %s %s: %s", request.method, upstream_url, exc)
        return JSONResponse(
            {"detail": "Upstream service unavailable"}, status_code=status.HTTP_502_BAD_GATEWAY
        )

    if upstream_response.status_code >= 500:
        # Centralized sanitization: whatever the backend actually said
        # (stack trace, DB error text, anything) is logged here and never
        # forwarded — the client only ever sees a generic message.
        logger.error(
            "upstream %s from %s %s: %s",
            upstream_response.status_code,
            request.method,
            upstream_url,
            upstream_response.text,
        )
        return JSONResponse(
            {"detail": "Internal server error"}, status_code=upstream_response.status_code
        )

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=_forward_headers(upstream_response.headers),
    )
