import uuid
from datetime import UTC, datetime

from analytics_service.models import ChatInteractionEventRow, LLMUsageEventRow
from sqlalchemy import select

from events import ChatInteractionEvent, LLMUsageEvent
from tenancy import reset_current_tenant_id, set_current_tenant_id


async def test_handle_llm_usage_event_writes_row_under_correct_tenant(session_factory):
    from analytics_service.ingestion import handle_llm_usage_event

    tenant_id = uuid.uuid4()
    event = LLMUsageEvent(
        tenant_id=tenant_id,
        employee_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        provider="anthropic",
        model="claude-sonnet-5",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.0123,
        created_at=datetime.now(UTC),
    )

    await handle_llm_usage_event(event.model_dump_json().encode())

    token = set_current_tenant_id(tenant_id)
    try:
        async with session_factory() as session:
            rows = (await session.execute(select(LLMUsageEventRow))).scalars().all()
    finally:
        reset_current_tenant_id(token)

    assert len(rows) == 1
    assert rows[0].employee_id == event.employee_id
    assert rows[0].model == "claude-sonnet-5"
    assert rows[0].cost_usd == 0.0123


async def test_handle_llm_usage_event_is_tenant_isolated(session_factory):
    from analytics_service.ingestion import handle_llm_usage_event

    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    for tenant_id in (tenant_a, tenant_b):
        event = LLMUsageEvent(
            tenant_id=tenant_id,
            employee_id=uuid.uuid4(),
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
        )
        await handle_llm_usage_event(event.model_dump_json().encode())

    token = set_current_tenant_id(tenant_a)
    try:
        async with session_factory() as session:
            rows = (await session.execute(select(LLMUsageEventRow))).scalars().all()
    finally:
        reset_current_tenant_id(token)

    assert len(rows) == 1


async def test_handle_chat_interaction_event_writes_row(session_factory):
    from analytics_service.ingestion import handle_chat_interaction_event

    tenant_id = uuid.uuid4()
    event = ChatInteractionEvent(
        tenant_id=tenant_id,
        employee_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        success=False,
        error_stage="llm",
        latency_ms=842,
    )

    await handle_chat_interaction_event(event.model_dump_json().encode())

    token = set_current_tenant_id(tenant_id)
    try:
        async with session_factory() as session:
            rows = (await session.execute(select(ChatInteractionEventRow))).scalars().all()
    finally:
        reset_current_tenant_id(token)

    assert len(rows) == 1
    assert rows[0].success is False
    assert rows[0].error_stage == "llm"
    assert rows[0].latency_ms == 842


async def test_handle_llm_usage_event_bad_payload_raises(session_factory):
    import pytest
    from analytics_service.ingestion import handle_llm_usage_event
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        await handle_llm_usage_event(b"not valid json")
