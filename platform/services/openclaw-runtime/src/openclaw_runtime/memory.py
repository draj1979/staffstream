"""Phase 4 stub. The real Memory Service (per-employee conversation and
long-term memory) lands here — until then, every chat turn starts with no
prior history, and storing a turn is a no-op. Callers already pass
tenant_id/employee_id so wiring in the real service later is a drop-in
replacement of this module, not a change to callers.
"""

import uuid


async def load_conversation_history(tenant_id: uuid.UUID, employee_id: uuid.UUID) -> list[dict]:
    return []


async def store_turn(
    tenant_id: uuid.UUID, employee_id: uuid.UUID, *, user_message: str, assistant_reply: str
) -> None:
    return None
