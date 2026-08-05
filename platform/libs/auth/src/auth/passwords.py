import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False


# Argon2 is deliberately slow (that's what makes it resistant to
# brute-forcing) — tens of milliseconds of pure CPU per call. Calling the
# sync functions above directly from an `async def` route runs that on
# the single event loop thread, serializing every concurrent
# signup/login in the process behind each other: a Phase 10 load test
# (scripts/load_test.py) showed exactly this — signup p95 latency scaling
# with concurrency far more than the DB pool size could explain, because
# the DB was never the bottleneck, argon2 blocking the loop was. Routes
# should use these, not the sync versions, so hashing runs in a thread
# and concurrent requests actually overlap.
async def hash_password_async(password: str) -> str:
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(verify_password, password, password_hash)
