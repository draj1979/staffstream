import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    tenant_id: uuid.UUID
    scope: str  # "user" | "system"
    employee_id: uuid.UUID | None = None  # None for "system"-scoped tokens
