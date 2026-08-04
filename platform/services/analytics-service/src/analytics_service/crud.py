"""Aggregated at query time, not via a scheduled rollup — simplest thing
that's correct at the data volumes a walking skeleton actually sees. If
raw-event scans ever get slow, the natural next step is a scheduled job
maintaining summary tables (or Postgres materialized views), not a
rewrite of these functions' callers.
"""

import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ChatInteractionEventRow, LLMUsageEventRow


def date_bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(from_date, time.min, tzinfo=UTC),
        datetime.combine(to_date, time.max, tzinfo=UTC),
    )


async def admin_summary(db: AsyncSession, from_date: date, to_date: date) -> dict:
    start, end = date_bounds(from_date, to_date)

    chat_row = (
        await db.execute(
            select(
                func.count().label("total"),
                func.sum(case((ChatInteractionEventRow.success.is_(True), 1), else_=0)).label(
                    "successes"
                ),
                func.count(func.distinct(ChatInteractionEventRow.employee_id)).label(
                    "active_employees"
                ),
                func.count(func.distinct(ChatInteractionEventRow.agent_id)).label(
                    "active_agents"
                ),
            ).where(
                ChatInteractionEventRow.created_at >= start,
                ChatInteractionEventRow.created_at <= end,
            )
        )
    ).one()

    usage_row = (
        await db.execute(
            select(
                func.coalesce(func.sum(LLMUsageEventRow.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(LLMUsageEventRow.output_tokens), 0).label(
                    "output_tokens"
                ),
                func.coalesce(func.sum(LLMUsageEventRow.cost_usd), 0.0).label("cost_usd"),
            ).where(
                LLMUsageEventRow.created_at >= start,
                LLMUsageEventRow.created_at <= end,
            )
        )
    ).one()

    total = chat_row.total or 0
    successes = chat_row.successes or 0
    return {
        "total_conversations": total,
        "success_rate": (successes / total) if total else 1.0,
        "active_employees": chat_row.active_employees or 0,
        "active_agents": chat_row.active_agents or 0,
        "total_input_tokens": usage_row.input_tokens,
        "total_output_tokens": usage_row.output_tokens,
        "total_cost_usd": usage_row.cost_usd,
    }


async def finance_summary(
    db: AsyncSession, from_date: date, to_date: date, *, top_n: int = 20
) -> dict:
    start, end = date_bounds(from_date, to_date)

    totals_row = (
        await db.execute(
            select(
                func.coalesce(func.sum(LLMUsageEventRow.cost_usd), 0.0).label("cost_usd"),
                func.coalesce(func.sum(LLMUsageEventRow.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(LLMUsageEventRow.output_tokens), 0).label(
                    "output_tokens"
                ),
            ).where(
                LLMUsageEventRow.created_at >= start,
                LLMUsageEventRow.created_at <= end,
            )
        )
    ).one()

    by_model = (
        await db.execute(
            select(
                LLMUsageEventRow.model,
                func.count().label("call_count"),
                func.coalesce(func.sum(LLMUsageEventRow.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(LLMUsageEventRow.output_tokens), 0).label(
                    "output_tokens"
                ),
                func.coalesce(func.sum(LLMUsageEventRow.cost_usd), 0.0).label("cost_usd"),
            )
            .where(LLMUsageEventRow.created_at >= start, LLMUsageEventRow.created_at <= end)
            .group_by(LLMUsageEventRow.model)
            .order_by(func.sum(LLMUsageEventRow.cost_usd).desc())
        )
    ).all()

    by_employee = (
        await db.execute(
            select(
                LLMUsageEventRow.employee_id,
                func.count().label("call_count"),
                func.coalesce(func.sum(LLMUsageEventRow.cost_usd), 0.0).label("cost_usd"),
            )
            .where(LLMUsageEventRow.created_at >= start, LLMUsageEventRow.created_at <= end)
            .group_by(LLMUsageEventRow.employee_id)
            .order_by(func.sum(LLMUsageEventRow.cost_usd).desc())
            .limit(top_n)
        )
    ).all()

    day_expr = func.date(LLMUsageEventRow.created_at)
    daily = (
        await db.execute(
            select(
                day_expr.label("day"),
                func.coalesce(func.sum(LLMUsageEventRow.cost_usd), 0.0).label("cost_usd"),
            )
            .where(LLMUsageEventRow.created_at >= start, LLMUsageEventRow.created_at <= end)
            .group_by(day_expr)
            .order_by(day_expr)
        )
    ).all()

    return {
        "total_cost_usd": totals_row.cost_usd,
        "total_input_tokens": totals_row.input_tokens,
        "total_output_tokens": totals_row.output_tokens,
        "cost_by_model": [
            {
                "model": r.model,
                "call_count": r.call_count,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": r.cost_usd,
            }
            for r in by_model
        ],
        "cost_by_employee": [
            {"employee_id": r.employee_id, "call_count": r.call_count, "cost_usd": r.cost_usd}
            for r in by_employee
        ],
        "daily_cost": [{"day": str(r.day), "cost_usd": r.cost_usd} for r in daily],
    }


def _percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(int(len(ordered) * pct), len(ordered) - 1)
    return float(ordered[index])


async def it_summary(db: AsyncSession, from_date: date, to_date: date) -> dict:
    start, end = date_bounds(from_date, to_date)

    rows = (
        await db.execute(
            select(
                ChatInteractionEventRow.agent_id,
                ChatInteractionEventRow.latency_ms,
                ChatInteractionEventRow.success,
                ChatInteractionEventRow.error_stage,
            ).where(
                ChatInteractionEventRow.created_at >= start,
                ChatInteractionEventRow.created_at <= end,
            )
        )
    ).all()

    total = len(rows)
    errors = [r for r in rows if not r.success]
    latencies = [r.latency_ms for r in rows]

    by_agent: dict[uuid.UUID, dict] = {}
    for r in rows:
        if r.agent_id is None:
            continue
        bucket = by_agent.setdefault(
            r.agent_id, {"request_count": 0, "error_count": 0, "latencies": []}
        )
        bucket["request_count"] += 1
        if not r.success:
            bucket["error_count"] += 1
        bucket["latencies"].append(r.latency_ms)

    by_stage: dict[str, int] = {}
    for r in errors:
        stage = r.error_stage or "unknown"
        by_stage[stage] = by_stage.get(stage, 0) + 1

    return {
        "total_requests": total,
        "error_rate": (len(errors) / total) if total else 0.0,
        "avg_latency_ms": (sum(latencies) / total) if total else 0.0,
        "p95_latency_ms": _percentile(latencies, 0.95),
        "requests_by_agent": [
            {
                "agent_id": agent_id,
                "request_count": bucket["request_count"],
                "error_count": bucket["error_count"],
                "avg_latency_ms": sum(bucket["latencies"]) / len(bucket["latencies"]),
            }
            for agent_id, bucket in by_agent.items()
        ],
        "errors_by_stage": [
            {"error_stage": stage, "count": count} for stage, count in by_stage.items()
        ],
    }
