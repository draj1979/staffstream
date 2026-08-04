import time
import uuid

import jwt as pyjwt
import pytest
from auth.config import JWT_ALGORITHM, JWT_SECRET_KEY

from auth import InvalidTokenError, decode_token, encode_access_token, encode_system_token


def test_access_token_round_trips_tenant_and_employee():
    tenant_id, employee_id = uuid.uuid4(), uuid.uuid4()
    token = encode_access_token(tenant_id, employee_id)

    claims = decode_token(token)
    assert claims["tenant_id"] == str(tenant_id)
    assert claims["sub"] == str(employee_id)
    assert claims["scope"] == "user"


def test_system_token_has_system_scope_and_no_employee():
    tenant_id = uuid.uuid4()
    token = encode_system_token(tenant_id)

    claims = decode_token(token)
    assert claims["tenant_id"] == str(tenant_id)
    assert claims["scope"] == "system"
    assert claims["sub"] == "system"


def test_decode_rejects_garbage_token():
    with pytest.raises(InvalidTokenError):
        decode_token("not-a-real-token")


def test_decode_rejects_expired_token():
    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "scope": "user",
        "type": "access",
        "iat": now - 120,
        "exp": now - 60,
        "jti": str(uuid.uuid4()),
    }
    expired = pyjwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    with pytest.raises(InvalidTokenError):
        decode_token(expired)


def test_decode_rejects_token_signed_with_wrong_secret():
    payload = {
        "sub": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "scope": "user",
        "type": "access",
        "exp": int(time.time()) + 60,
    }
    forged = pyjwt.encode(payload, "someone-elses-secret", algorithm=JWT_ALGORITHM)
    with pytest.raises(InvalidTokenError):
        decode_token(forged)
