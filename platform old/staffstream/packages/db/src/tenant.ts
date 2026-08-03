import { neonConfig, Pool } from '@neondatabase/serverless'
import { sql } from 'drizzle-orm'
import { drizzle } from 'drizzle-orm/neon-serverless'
import ws from 'ws'
import * as schema from './schema'

// The default `db` export (./index.ts) uses the neon-http driver, which is a
// stateless HTTP call per query and has no transaction support ("No transactions
// support in neon-http driver"). `SET LOCAL` only lives for the duration of a
// transaction, so tenant scoping requires a driver that can hold one open —
// hence a separate websocket-based (neon-serverless) client here.
neonConfig.webSocketConstructor = ws

const pool = new Pool({ connectionString: process.env.DATABASE_URL! })
const tenantDb = drizzle(pool, { schema })

export type TenantTx = Parameters<Parameters<typeof tenantDb.transaction>[0]>[0]

/**
 * Runs `fn` inside a transaction with `app.company_id` set via SET LOCAL
 * (through set_config, which is parameterizable) so row-level security
 * policies scoped to `current_setting('app.company_id')` apply to every
 * query `fn` issues. Must be called per-request — the setting does not
 * survive past the transaction.
 */
export async function withTenantContext<T>(
  companyId: string,
  fn: (tx: TenantTx) => Promise<T>
): Promise<T> {
  return tenantDb.transaction(async (tx) => {
    await tx.execute(sql`select set_config('app.company_id', ${companyId}, true)`)
    return fn(tx)
  })
}
