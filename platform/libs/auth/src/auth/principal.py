import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    tenant_id: uuid.UUID
    scope: str  # "user" | "system"
    employee_id: uuid.UUID | None = None  # None for "system"-scoped tokens
    # None for "system"-scoped tokens — there's no individual actor to rank.
    # "user"-scoped tokens always carry a role, defaulting to "employee" if
    # the JWT predates this claim or the employee has no recognized role.
    role: str | None = None
