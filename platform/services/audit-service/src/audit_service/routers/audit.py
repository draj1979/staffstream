import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth import Principal, Role, require_role

from .. import crud
from ..db import get_db
from ..schemas import AuditLogEntryOut

router = APIRouter(tags=["audit"])

# Only admins can read the audit trail — the platform's own security/
# compliance record shouldn't be visible to every employee by default.
# No route in this router (or crud.py) can update or delete a row.
admin_auth = require_role(Role.ADMIN.value)


@router.get("/audit-logs", response_model=list[AuditLogEntryOut])
async def list_audit_logs(
    action: str | None = None,
    target_type: str | None = None,
    actor_employee_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
    principal: Principal = Depends(admin_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_audit_logs(
        db,
        action=action,
        target_type=target_type,
        actor_employee_id=actor_employee_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
