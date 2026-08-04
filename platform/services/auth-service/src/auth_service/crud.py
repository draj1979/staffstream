import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Credential, RefreshToken


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def get_credential_by_email(db: AsyncSession, email: str) -> Credential | None:
    result = await db.execute(select(Credential).where(Credential.email == email))
    return result.scalar_one_or_none()


async def create_credential(
    db: AsyncSession, *, employee_id: uuid.UUID, email: str, password_hash: str
) -> Credential:
    credential = Credential(employee_id=employee_id, email=email, password_hash=password_hash)
    db.add(credential)
    await db.commit()
    await db.refresh(credential)
    return credential


async def create_refresh_token(
    db: AsyncSession, *, employee_id: uuid.UUID, raw_token: str, expires_at: datetime
) -> RefreshToken:
    token = RefreshToken(
        employee_id=employee_id,
        token_hash=hash_token(raw_token),
        expires_at=expires_at,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


async def get_active_refresh_token(db: AsyncSession, raw_token: str) -> RefreshToken | None:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    )
    token = result.scalar_one_or_none()
    if token is None:
        return None
    if token.revoked_at is not None:
        return None
    expires_at = token.expires_at
    if expires_at.tzinfo is None:  # sqlite (tests) drops tzinfo on round-trip; Postgres doesn't
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        return None
    return token


async def revoke_refresh_token(db: AsyncSession, token: RefreshToken) -> None:
    token.revoked_at = datetime.now(UTC)
    await db.commit()
