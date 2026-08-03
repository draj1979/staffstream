import { db, schema } from '@staffstream/db'
import { eq } from 'drizzle-orm'
import { NextRequest } from 'next/server'
import { afterAll, describe, expect, it } from 'vitest'
import { POST } from './route'

// Hits the real Neon dev database configured in .env.local — there's no
// separate test DB/branch provisioned yet. Every row this test creates is
// deleted in afterAll so it doesn't leave junk behind, but a genuinely
// isolated test DB (e.g. a dedicated Neon branch) would be a safer setup.
const createdIds: string[] = []

function postRequest(body: unknown) {
  return new NextRequest('http://localhost:3000/api/admin/companies', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
}

describe('POST /api/admin/companies (integration)', () => {
  afterAll(async () => {
    for (const id of createdIds) {
      await db.delete(schema.companies).where(eq(schema.companies.id, id))
    }
  })

  it('creates a company and returns id, name, code', async () => {
    const res = await POST(postRequest({ name: 'Litmus Automations Test' }))
    expect(res.status).toBe(201)

    const json = await res.json()
    createdIds.push(json.id)

    expect(json.id).toEqual(expect.any(String))
    expect(json.name).toBe('Litmus Automations Test')
    expect(json.code).toMatch(/^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}$/)

    const [row] = await db.select().from(schema.companies).where(eq(schema.companies.id, json.id))
    expect(row).toBeDefined()
    expect(row!.code).toBe(json.code)
    expect(row!.name).toBe('Litmus Automations Test')
  })

  it('rejects a name shorter than 2 characters', async () => {
    const res = await POST(postRequest({ name: 'A' }))
    expect(res.status).toBe(400)
    expect((await res.json()).error).toBe('invalid_input')
  })

  it('rejects a missing name', async () => {
    const res = await POST(postRequest({}))
    expect(res.status).toBe(400)
  })

  it('rejects malformed JSON', async () => {
    const req = new NextRequest('http://localhost:3000/api/admin/companies', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: '{not json',
    })
    const res = await POST(req)
    expect(res.status).toBe(400)
  })

  it('assigns different codes to companies created back-to-back', async () => {
    const [res1, res2] = await Promise.all([
      POST(postRequest({ name: 'Dup Test Co A' })),
      POST(postRequest({ name: 'Dup Test Co B' })),
    ])
    const [json1, json2] = await Promise.all([res1.json(), res2.json()])
    createdIds.push(json1.id, json2.id)
    expect(json1.code).not.toBe(json2.code)
  })
})
