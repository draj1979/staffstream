import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .crypto import encrypt_secret
from .models import Credential, RefreshToken, SsoConnection


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


async def get_sso_connection(db: AsyncSession, provider: str) -> SsoConnection | None:
    result = await db.execute(select(SsoConnection).where(SsoConnection.provider == provider))
    return result.scalar_one_or_none()


async def list_sso_connections(db: AsyncSession) -> list[SsoConnection]:
    result = await db.execute(select(SsoConnection))
    return list(result.scalars().all())


async def upsert_sso_connection(
    db: AsyncSession,
    provider: str,
    *,
    client_id: str,
    client_secret: str,
    issuer_domain: str | None,
    hosted_domain: str | None,
    enabled: bool,
) -> SsoConnection:
    existing = await get_sso_connection(db, provider)
    encrypted = encrypt_secret(client_secret)
    if existing is not None:
        existing.client_id = client_id
        existing.client_secret_encrypted = encrypted
        existing.issuer_domain = issuer_domain
        existing.hosted_domain = hosted_domain
        existing.enabled = enabled
        await db.commit()
        await db.refresh(existing)
        return existing

    connection = SsoConnection(
        provider=provider,
        client_id=client_id,
        client_secret_encrypted=encrypted,
        issuer_domain=issuer_domain,
        hosted_domain=hosted_domain,
        enabled=enabled,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection
