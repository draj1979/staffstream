import path from 'node:path'
import { config } from 'dotenv'

// @staffstream/db reads process.env.DATABASE_URL at import time, and Vitest
// doesn't load .env.local into process.env the way Next.js does — this has
// to happen before any test file imports a route handler.
config({ path: path.resolve(__dirname, '.env.local') })
