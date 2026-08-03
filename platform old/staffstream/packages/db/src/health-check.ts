import { sql } from 'drizzle-orm'
import { db } from './index'

export async function checkDbConnection(): Promise<boolean> {
  await db.execute(sql`select 1`)
  return true
}

if (import.meta.url === `file://${process.argv[1]}`) {
  checkDbConnection()
    .then(() => {
      console.log('DB connected')
      process.exit(0)
    })
    .catch((err) => {
      console.error('DB connection failed:', err)
      process.exit(1)
    })
}
