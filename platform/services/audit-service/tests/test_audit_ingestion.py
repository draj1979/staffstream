import uuid

import pytest
from audit_service.models import AuditLogEntry
from pydantic import ValidationError
from sqlalchemy import select

from events import AuditEvent
from tenancy import reset_current_tenant_id, set_current_tenant_id


async def test_handle_audit_event_writes_row_under_correct_tenant(session_factory):
    from audit_service.ingestion import handle_audit_event

    tenant_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_employee_id=actor_id,
        action="employee.updated",
        target_type="employee",
        target_id=str(uuid.uuid4()),
        metadata={"field": "department"},
    )

    await handle_audit_event(event.model_dump_json().encode())

    token = set_current_tenant_id(tenant_id)
    try:
        async with session_factory() as session:
            rows = (await session.execute(select(AuditLogEntry))).scalars().all()
    finally:
        reset_current_tenant_id(token)

    assert len(rows) == 1
    assert rows[0].actor_employee_id == actor_id
    assert rows[0].action == "employee.updated"
    assert rows[0].entry_metadata == {"field": "department"}


async def test_handle_audit_event_is_tenant_isolated(session_factory):
    from audit_service.ingestion import handle_audit_event

    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    for tenant_id in (tenant_a, tenant_b):
        event = AuditEvent(tenant_id=tenant_id, action="tenant.updated", target_type="tenant")
        await handle_audit_event(event.model_dump_json().encode())

    token = set_current_tenant_id(tenant_a)
    try:
        async with session_factory() as session:
            rows = (await session.execute(select(AuditLogEntry))).scalars().all()
    finally:
        reset_current_tenant_id(token)

    assert len(rows) == 1


async def test_handle_audit_event_bad_payload_raises(session_factory):
    from audit_service.ingestion import handle_audit_event

    with pytest.raises(ValidationError):
        await handle_audit_event(b"not valid json")
