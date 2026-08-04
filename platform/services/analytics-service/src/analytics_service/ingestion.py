"""Message handlers — one per event type, called by the background
consumer tasks (see consumer.py). Each sets the tenant context from the
event payload itself (there's no JWT here, this isn't a request), writes
one row, and resets the context. A parse or DB error propagates back to
events.consume(), which logs it and drops the message rather than
retrying forever.
"""

from events import ChatInteractionEvent, LLMUsageEvent
from tenancy import reset_current_tenant_id, set_current_tenant_id

from .db import SessionFactory
from .models import ChatInteractionEventRow, LLMUsageEventRow


async def handle_llm_usage_event(body: bytes) -> None:
    event = LLMUsageEvent.model_validate_json(body)
    token = set_current_tenant_id(event.tenant_id)
    try:
        async with SessionFactory() as session:
            session.add(
                LLMUsageEventRow(
                    employee_id=event.employee_id,
                    agent_id=event.agent_id,
                    provider=event.provider,
                    model=event.model,
                    input_tokens=event.input_tokens,
                    output_tokens=event.output_tokens,
                    cost_usd=event.cost_usd,
                    created_at=event.created_at,
                )
            )
            await session.commit()
    finally:
        reset_current_tenant_id(token)


async def handle_chat_interaction_event(body: bytes) -> None:
    event = ChatInteractionEvent.model_validate_json(body)
    token = set_current_tenant_id(event.tenant_id)
    try:
        async with SessionFactory() as session:
            session.add(
                ChatInteractionEventRow(
                    employee_id=event.employee_id,
                    agent_id=event.agent_id,
                    success=event.success,
                    error_stage=event.error_stage,
                    latency_ms=event.latency_ms,
                    created_at=event.created_at,
                )
            )
            await session.commit()
    finally:
        reset_current_tenant_id(token)
