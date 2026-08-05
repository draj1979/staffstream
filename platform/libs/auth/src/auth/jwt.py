import uuid
from datetime import UTC, datetime, timedelta

import jwt

from .config import (
    ACCESS_TOKEN_TTL_SECONDS,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    SYSTEM_TOKEN_TTL_SECONDS,
)
from .errors import InvalidTokenError


def encode_access_token(
    tenant_id: uuid.UUID, employee_id: uuid.UUID, role: str = "employee"
) -> str:
    return _encode(
        {
            "sub": str(employee_id),
            "tenant_id": str(tenant_id),
            "scope": "user",
            "role": role,
        },
        ttl_seconds=ACCESS_TOKEN_TTL_SECONDS,
    )


def encode_system_token(tenant_id: uuid.UUID) -> str:
    """A short-lived token minted only by auth-service, for the one
    service-to-service call (creating the first employee during signup)
    that must happen before any user has credentials to authenticate with."""
    return _encode(
        {
            "sub": "system",
            "tenant_id": str(tenant_id),
            "scope": "system",
        },
        ttl_seconds=SYSTEM_TOKEN_TTL_SECONDS,
    )


def encode_state_token(claims: dict, *, ttl_seconds: int = 600) -> str:
    """Generic short-lived signed token for state that has to survive a
    round trip through a third party — e.g. an OAuth `state` parameter,
    which a redirect handler must be able to trust wasn't forged by
    whoever lands on the callback URL. Not Principal-shaped like an
    access/system token; just arbitrary claims signed with the same
    shared secret, decoded with the plain `decode_token` above."""
    return _encode({**claims, "purpose": "state"}, ttl_seconds=ttl_seconds)


def _encode(claims: dict, *, ttl_seconds: int) -> str:
    now = datetime.now(UTC)
    payload = {
        **claims,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
