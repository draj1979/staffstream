"""Phase 10 multi-tenant load test.

Simulates many tenants signing up and using the platform concurrently,
all through the API Gateway (the same path real traffic takes), and
checks the two things Phase 10 asked to be verified under load:

1. Tenant isolation holds under concurrency — every tenant sees only its
   own employees, even while dozens of tenants are being created and
   queried in parallel (this exercises libs/tenancy's with_loader_criteria
   injection under real concurrent DB access, not just single-request
   tests).
2. Per-tenant rate limiting engages correctly — one tenant hammering the
   gateway gets throttled (429) without affecting a different tenant's
   own request budget (proving the Redis bucket key is actually
   per-tenant, not global).

Run against the local stack (services started per README's "Local dev"
section, or via the five uvicorn processes this script assumes are
already up): tenant-service, employee-service, auth-service,
agent-registry, api-gateway on their standard ports.

Usage:
    uv run python scripts/load_test.py --tenants 30 --concurrency 10
"""

import argparse
import asyncio
import time
import uuid

import httpx

GATEWAY_URL = "http://localhost:8000"


class LatencyBucket:
    def __init__(self) -> None:
        self.samples: list[float] = []
        self.errors: list[str] = []

    def record(self, elapsed: float) -> None:
        self.samples.append(elapsed)

    def summary(self) -> str:
        if not self.samples:
            return "no samples"
        s = sorted(self.samples)
        p50 = s[len(s) // 2]
        p95 = s[int(len(s) * 0.95) - 1] if len(s) > 1 else s[0]
        return (
            f"n={len(s)} min={s[0]*1000:.1f}ms p50={p50*1000:.1f}ms "
            f"p95={p95*1000:.1f}ms max={s[-1]*1000:.1f}ms"
        )


async def create_tenant(client: httpx.AsyncClient, bucket: LatencyBucket, idx: int) -> dict:
    t0 = time.monotonic()
    resp = await client.post(
        f"{GATEWAY_URL}/tenants",
        json={"company_name": f"Load Test Co {idx}-{uuid.uuid4().hex[:8]}"},
    )
    bucket.record(time.monotonic() - t0)
    if resp.status_code != 201:
        bucket.errors.append(f"create_tenant[{idx}]: {resp.status_code} {resp.text[:200]}")
        return {}
    return resp.json()


async def signup_employee(
    client: httpx.AsyncClient, bucket: LatencyBucket, tenant_id: str, idx: int
) -> dict:
    t0 = time.monotonic()
    resp = await client.post(
        f"{GATEWAY_URL}/auth/signup",
        headers={"X-Tenant-Id": tenant_id},
        json={
            "email": f"employee{idx}@loadtest-{tenant_id[:8]}.example.com",
            "password": "correct-horse-battery-staple",
            "roles": ["admin"],  # first signup per tenant is its own admin
        },
    )
    bucket.record(time.monotonic() - t0)
    if resp.status_code != 201:
        bucket.errors.append(f"signup[{tenant_id}]: {resp.status_code} {resp.text[:200]}")
        return {}
    return resp.json()


async def list_own_employees(
    client: httpx.AsyncClient, bucket: LatencyBucket, tenant_id: str, access_token: str
) -> list[dict]:
    t0 = time.monotonic()
    resp = await client.get(
        f"{GATEWAY_URL}/employees", headers={"Authorization": f"Bearer {access_token}"}
    )
    bucket.record(time.monotonic() - t0)
    if resp.status_code != 200:
        bucket.errors.append(f"list_employees[{tenant_id}]: {resp.status_code} {resp.text[:200]}")
        return []
    return resp.json()


async def phase_provision(
    client: httpx.AsyncClient, n_tenants: int, concurrency: int
) -> tuple[list[dict], LatencyBucket, LatencyBucket]:
    """Create N tenants and one employee (its admin) each, all concurrently
    (bounded by a semaphore so this behaves like N real signups arriving
    close together, not an unbounded connection storm)."""
    tenant_bucket, signup_bucket = LatencyBucket(), LatencyBucket()
    sem = asyncio.Semaphore(concurrency)

    async def provision_one(idx: int) -> dict:
        async with sem:
            tenant = await create_tenant(client, tenant_bucket, idx)
            if not tenant:
                return {}
            employee = await signup_employee(client, signup_bucket, tenant["tenant_id"], idx)
            if not employee:
                return {}
            return {
                "tenant_id": tenant["tenant_id"],
                "company_name": tenant["company_name"],
                "employee_id": employee["employee_id"],
                "access_token": employee["access_token"],
            }

    results = await asyncio.gather(*(provision_one(i) for i in range(n_tenants)))
    return [r for r in results if r], tenant_bucket, signup_bucket


async def phase_isolation_check(
    client: httpx.AsyncClient, tenants: list[dict], concurrency: int
) -> tuple[bool, LatencyBucket]:
    """Every tenant lists /employees concurrently. Each must see exactly
    its own one employee and nobody else's — the actual tenant-isolation
    assertion, exercised under concurrent cross-tenant traffic rather than
    one request at a time."""
    bucket = LatencyBucket()
    sem = asyncio.Semaphore(concurrency)
    isolation_ok = True

    async def check_one(tenant: dict) -> None:
        nonlocal isolation_ok
        async with sem:
            employees = await list_own_employees(
                client, bucket, tenant["tenant_id"], tenant["access_token"]
            )
        seen_ids = {e["employee_id"] for e in employees}
        if seen_ids != {tenant["employee_id"]}:
            isolation_ok = False
            print(
                f"  ISOLATION BREACH for tenant {tenant['tenant_id']}: "
                f"expected {{{tenant['employee_id']}}}, saw {seen_ids}"
            )

    await asyncio.gather(*(check_one(t) for t in tenants))
    return isolation_ok, bucket


async def phase_rate_limit_check(
    client: httpx.AsyncClient, hammered: dict, control: dict, burst: int
) -> bool:
    """Fire `burst` concurrent requests as one tenant (well past the
    gateway's default 120/60s budget) and confirm some get 429'd, while a
    second, quiet tenant's own request in the same window sails through
    untouched — proving the Redis bucket key really is per-tenant."""

    async def hit(tenant: dict) -> int:
        resp = await client.get(
            f"{GATEWAY_URL}/employees",
            headers={"Authorization": f"Bearer {tenant['access_token']}"},
        )
        return resp.status_code

    statuses = await asyncio.gather(*(hit(hammered) for _ in range(burst)))
    throttled = sum(1 for s in statuses if s == 429)
    ok = sum(1 for s in statuses if s == 200)
    print(f"  hammered tenant: {ok} succeeded, {throttled} throttled (429) out of {burst}")

    control_status = await hit(control)
    control_ok = control_status == 200
    control_label = "OK" if control_ok else "UNEXPECTEDLY THROTTLED"
    print(f"  control tenant (different bucket): status={control_status} ({control_label})")

    return throttled > 0 and control_ok


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenants", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--rate-limit-burst", type=int, default=150)
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"=== Provisioning {args.tenants} tenants (concurrency={args.concurrency}) ===")
        t0 = time.monotonic()
        tenants, tenant_bucket, signup_bucket = await phase_provision(
            client, args.tenants, args.concurrency
        )
        elapsed = time.monotonic() - t0
        print(f"  provisioned {len(tenants)}/{args.tenants} tenants in {elapsed:.2f}s")
        print(f"  POST /tenants:    {tenant_bucket.summary()}")
        print(f"  POST /auth/signup: {signup_bucket.summary()}")
        if tenant_bucket.errors:
            print(f"  tenant errors (first 5): {tenant_bucket.errors[:5]}")
        if signup_bucket.errors:
            print(f"  signup errors (first 5): {signup_bucket.errors[:5]}")

        if len(tenants) < 2:
            print("Not enough tenants provisioned to continue — aborting.")
            return

        print(f"\n=== Tenant isolation check under concurrency ({len(tenants)} tenants) ===")
        isolation_ok, list_bucket = await phase_isolation_check(client, tenants, args.concurrency)
        print(f"  GET /employees:   {list_bucket.summary()}")
        if isolation_ok:
            print("  Result: PASS — every tenant saw only its own data")
        else:
            print("  Result: FAIL — see breaches above")

        print(f"\n=== Per-tenant rate limiting check (burst={args.rate_limit_burst}) ===")
        rate_ok = await phase_rate_limit_check(
            client, hammered=tenants[0], control=tenants[1], burst=args.rate_limit_burst
        )
        if rate_ok:
            print("  Result: PASS — throttling engaged, other tenant unaffected")
        else:
            print("  Result: FAIL")

        print("\n=== Summary ===")
        print(f"Isolation: {'PASS' if isolation_ok else 'FAIL'}")
        print(f"Rate limiting: {'PASS' if rate_ok else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
