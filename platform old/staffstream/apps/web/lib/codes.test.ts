import { describe, expect, it } from 'vitest'
import { generateCompanyCode } from './codes'

describe('generateCompanyCode', () => {
  it('returns a 6-character string', () => {
    expect(generateCompanyCode()).toHaveLength(6)
  })

  it('only uses uppercase letters and digits, excluding ambiguous characters', () => {
    for (let i = 0; i < 200; i++) {
      expect(generateCompanyCode()).toMatch(/^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}$/)
    }
  })

  it('never contains 0, 1, I, O, or L', () => {
    for (let i = 0; i < 200; i++) {
      expect(generateCompanyCode()).not.toMatch(/[01IOL]/)
    }
  })

  it('is deterministic given a fixed random source', () => {
    const always0 = () => 0
    expect(generateCompanyCode(always0)).toBe('AAAAAA')

    const alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    const almostOne = () => 1 - Number.EPSILON
    expect(generateCompanyCode(almostOne)).toBe(alphabet.at(-1)!.repeat(6))
  })

  it('produces varied output across many calls', () => {
    const codes = new Set(Array.from({ length: 500 }, () => generateCompanyCode()))
    // 500 draws from a ~1B-combination space should essentially never collide;
    // this just guards against a broken generator that always returns the same code.
    expect(codes.size).toBeGreaterThan(490)
  })
})
