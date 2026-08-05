import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .connectors import TokenSet
from .crypto import encrypt_token
from .models import EmployeeConnection, Skill, TenantSkillEnablement


async def list_skills(db: AsyncSession) -> list[Skill]:
    result = await db.execute(select(Skill).order_by(Skill.skill_id))
    return list(result.scalars().all())


async def get_skill(db: AsyncSession, skill_id: str) -> Skill | None:
    return await db.get(Skill, skill_id)


async def get_enablement(db: AsyncSession, skill_id: str) -> TenantSkillEnablement | None:
    result = await db.execute(
        select(TenantSkillEnablement).where(TenantSkillEnablement.skill_id == skill_id)
    )
    return result.scalar_one_or_none()


async def list_enablements(db: AsyncSession) -> dict[str, TenantSkillEnablement]:
    result = await db.execute(select(TenantSkillEnablement))
    return {row.skill_id: row for row in result.scalars().all()}


async def set_enablement(
    db: AsyncSession, skill_id: str, *, enabled: bool, config: dict
) -> TenantSkillEnablement:
    existing = await get_enablement(db, skill_id)
    if existing is not None:
        existing.enabled = enabled
        existing.config = config
        await db.commit()
        await db.refresh(existing)
        return existing

    row = TenantSkillEnablement(skill_id=skill_id, enabled=enabled, config=config)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def is_enabled(db: AsyncSession, skill_id: str) -> bool:
    enablement = await get_enablement(db, skill_id)
    return enablement is not None and enablement.enabled


async def get_connection(
    db: AsyncSession, employee_id: uuid.UUID, skill_id: str
) -> EmployeeConnection | None:
    result = await db.execute(
        select(EmployeeConnection).where(
            EmployeeConnection.employee_id == employee_id,
            EmployeeConnection.skill_id == skill_id,
        )
    )
    return result.scalar_one_or_none()


async def list_connections(db: AsyncSession, employee_id: uuid.UUID) -> list[EmployeeConnection]:
    result = await db.execute(
        select(EmployeeConnection).where(EmployeeConnection.employee_id == employee_id)
    )
    return list(result.scalars().all())


async def upsert_connection(
    db: AsyncSession, employee_id: uuid.UUID, skill_id: str, tokens: TokenSet
) -> EmployeeConnection:
    existing = await get_connection(db, employee_id, skill_id)
    encrypted_access = encrypt_token(tokens.access_token)
    encrypted_refresh = encrypt_token(tokens.refresh_token) if tokens.refresh_token else None

    if existing is not None:
        existing.access_token_encrypted = encrypted_access
        existing.refresh_token_encrypted = encrypted_refresh
        existing.token_expires_at = tokens.expires_at
        existing.granted_scope = tokens.scope
        existing.external_account = tokens.external_account
        existing.connection_metadata = tokens.extra
        await db.commit()
        await db.refresh(existing)
        return existing

    row = EmployeeConnection(
        employee_id=employee_id,
        skill_id=skill_id,
        access_token_encrypted=encrypted_access,
        refresh_token_encrypted=encrypted_refresh,
        token_expires_at=tokens.expires_at,
        granted_scope=tokens.scope,
        external_account=tokens.external_account,
        connection_metadata=tokens.extra,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_connection_tokens(
    db: AsyncSession, connection: EmployeeConnection, tokens: TokenSet
) -> EmployeeConnection:
    connection.access_token_encrypted = encrypt_token(tokens.access_token)
    if tokens.refresh_token:
        connection.refresh_token_encrypted = encrypt_token(tokens.refresh_token)
    connection.token_expires_at = tokens.expires_at
    if tokens.scope:
        connection.granted_scope = tokens.scope
    if tokens.extra:
        connection.connection_metadata = tokens.extra
    await db.commit()
    await db.refresh(connection)
    return connection


async def delete_connection(db: AsyncSession, connection: EmployeeConnection) -> None:
    await db.delete(connection)
    await db.commit()


def token_needs_refresh(
    connection: EmployeeConnection, *, now: datetime, skew_seconds: int = 60
) -> bool:
    if connection.token_expires_at is None:
        return False
    expires_at = connection.token_expires_at
    if expires_at.tzinfo is None:
        # SQLite round-trips naive datetimes; treat as UTC like everywhere else.
        expires_at = expires_at.replace(tzinfo=UTC)
    return (expires_at - now).total_seconds() < skew_seconds
