"""Message handler for the one event type this service cares about,
called by the background consumer task (see consumer.py). Sets the
tenant context from the event payload itself (there's no JWT here, this
isn't a request), writes one immutable row, and resets the context. A
parse or DB error propagates back to events.consume(), which logs it and
drops the message rather than retrying forever.
"""

from events import AuditEvent
from tenancy import reset_current_tenant_id, set_current_tenant_id

from .db import SessionFactory
from .models import AuditLogEntry


async def handle_audit_event(body: bytes) -> None:
    event = AuditEvent.model_validate_json(body)
    token = set_current_tenant_id(event.tenant_id)
    try:
        async with SessionFactory() as session:
            session.add(
                AuditLogEntry(
                    actor_employee_id=event.actor_employee_id,
                    action=event.action,
                    target_type=event.target_type,
                    target_id=event.target_id,
                    entry_metadata=event.metadata,
                    created_at=event.created_at,
                )
            )
            await session.commit()
    finally:
        reset_current_tenant_id(token)
