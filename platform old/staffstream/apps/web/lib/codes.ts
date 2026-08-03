// Excludes visually ambiguous characters (0/O, 1/I/L) so codes are easy to
// read back over a phone call or a support ticket.
const ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
const CODE_LENGTH = 6

/**
 * Generates a 6-character uppercase alphanumeric code. Not guaranteed unique
 * on its own — callers that need uniqueness (e.g. company codes backed by a
 * DB unique constraint) should generate, attempt to persist, and retry on
 * conflict rather than trusting this in isolation.
 */
export function generateCompanyCode(random: () => number = Math.random): string {
  let code = ''
  for (let i = 0; i < CODE_LENGTH; i++) {
    code += ALPHABET[Math.floor(random() * ALPHABET.length)]
  }
  return code
}
