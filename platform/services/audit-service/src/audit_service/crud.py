import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditLogEntry


async def list_audit_logs(
    db: AsyncSession,
    *,
    action: str | None = None,
    target_type: str | None = None,
    actor_employee_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLogEntry]:
    query = select(AuditLogEntry)
    if action is not None:
        query = query.where(AuditLogEntry.action == action)
    if target_type is not None:
        query = query.where(AuditLogEntry.target_type == target_type)
    if actor_employee_id is not None:
        query = query.where(AuditLogEntry.actor_employee_id == actor_employee_id)
    if from_date is not None:
        query = query.where(AuditLogEntry.created_at >= from_date)
    if to_date is not None:
        query = query.where(AuditLogEntry.created_at <= to_date)

    query = query.order_by(AuditLogEntry.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())
