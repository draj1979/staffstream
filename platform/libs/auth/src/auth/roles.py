"""Fixed, three-tier role hierarchy — scoped per tenant by construction:
an employee's role only ever means something relative to their own
tenant_id, since Employee (and therefore its `roles` field) is itself a
tenant-scoped table. Admin implicitly has every permission manager has,
which has every permission employee has — `require_role` below checks
"at least this rank", not an exact match.
"""

import enum


class Role(enum.StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


ROLE_RANK: dict[str, int] = {
    Role.EMPLOYEE.value: 0,
    Role.MANAGER.value: 1,
    Role.ADMIN.value: 2,
}


def highest_role(roles: list[str]) -> str:
    """An Employee's `roles` field is a free-form list (Employee Service
    doesn't validate its contents) — this picks the highest-ranked
    recognized role for JWT embedding, defaulting to the least-privileged
    "employee" for an empty list or a list of unrecognized strings, so a
    fresh employee always has *some* JWT role rather than none."""
    known = [r for r in roles if r in ROLE_RANK]
    if not known:
        return Role.EMPLOYEE.value
    return max(known, key=lambda r: ROLE_RANK[r])


def role_satisfies(actual: str | None, minimum: str) -> bool:
    return ROLE_RANK.get(actual or "", -1) >= ROLE_RANK.get(minimum, 0)
