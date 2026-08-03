// Auth0 silently drops custom ID token claims that aren't namespaced under a URL.
// Populate these via an Auth0 Action (post-login) that reads the user's
// StaffStream employee/company record and adds them to the token.
export const AUTH0_CLAIM_NAMESPACE = 'https://staffstream.in/claims'
export const AUTH0_COMPANY_ID_CLAIM = `${AUTH0_CLAIM_NAMESPACE}/company_id`
export const AUTH0_ROLE_CLAIM = `${AUTH0_CLAIM_NAMESPACE}/role`

export type AppRole = 'admin' | 'employee'

export const HEADER_COMPANY_ID = 'x-company-id'
export const HEADER_USER_ROLE = 'x-user-role'
