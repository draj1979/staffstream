"""Three read-only dashboard endpoints per the HLD: Admin, Finance, IT.
All are tenant-scoped automatically via the tenancy query-filtering layer
(every query in crud.py hits TenantScopedBase tables). Fine-grained
role checks (e.g. only Finance sees /finance) are RBAC/ABAC, which is
Phase 9 — for now every authenticated employee in the tenant can read
every dashboard, same as the rest of the platform pre-Phase-9.
"""

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth import Principal, require_auth

from .. import crud
from ..db import get_db
from ..schemas import AdminDashboard, DateRange, FinanceDashboard, ITDashboard

router = APIRouter(prefix="/analytics", tags=["analytics"])
user_auth = require_auth()

DEFAULT_WINDOW_DAYS = 30


def _resolve_range(
    from_date: dt.date | None, to_date: dt.date | None
) -> tuple[dt.date, dt.date]:
    resolved_to = to_date or dt.datetime.now(dt.UTC).date()
    resolved_from = from_date or (resolved_to - dt.timedelta(days=DEFAULT_WINDOW_DAYS))
    return resolved_from, resolved_to


@router.get("/admin", response_model=AdminDashboard)
async def admin_dashboard(
    from_date: dt.date | None = None,
    to_date: dt.date | None = None,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    start, end = _resolve_range(from_date, to_date)
    summary = await crud.admin_summary(db, start, end)
    return AdminDashboard(range=DateRange(from_date=start, to_date=end), **summary)


@router.get("/finance", response_model=FinanceDashboard)
async def finance_dashboard(
    from_date: dt.date | None = None,
    to_date: dt.date | None = None,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    start, end = _resolve_range(from_date, to_date)
    summary = await crud.finance_summary(db, start, end)
    return FinanceDashboard(range=DateRange(from_date=start, to_date=end), **summary)


@router.get("/it", response_model=ITDashboard)
async def it_dashboard(
    from_date: dt.date | None = None,
    to_date: dt.date | None = None,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    start, end = _resolve_range(from_date, to_date)
    summary = await crud.it_summary(db, start, end)
    return ITDashboard(range=DateRange(from_date=start, to_date=end), **summary)
