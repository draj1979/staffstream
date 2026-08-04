"""Resolves who a request should be rate-limited as. This is deliberately
NOT authentication or authorization — the gateway never rejects a request
for having a missing/invalid/expired token; that's each backend service's
own job via require_auth. This only decides which bucket a request's
usage counts against, so one busy tenant can't starve every other tenant.

Verifying the JWT signature (rather than just decoding the claims
unchecked) means a client can't put an arbitrary tenant_id in an unsigned
token to dodge its own rate limit or attribute load to someone else's
bucket — worst case with an invalid/expired token, we just fall back to
the X-Tenant-Id header or the client IP.
"""

from starlette.requests import Request

from auth import InvalidTokenError, decode_token


def resolve_bucket_key(request: Request) -> str:
    authorization = request.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            claims = decode_token(token)
            return f"tenant:{claims['tenant_id']}"
        except InvalidTokenError:
            pass

    tenant_header = request.headers.get("x-tenant-id")
    if tenant_header:
        return f"tenant:{tenant_header}"

    client = request.client
    return f"ip:{client.host if client else 'unknown'}"
