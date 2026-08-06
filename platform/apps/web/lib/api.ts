import { apiRequest } from "./api-client";
import type {
  Agent,
  AuditLogEntryOut,
  ChatResponse,
  ConnectionOut,
  DocumentOut,
  DocumentScope,
  Employee,
  AdminAnalytics,
  FinanceAnalytics,
  ItAnalytics,
  MemoryTurn,
  Role,
  SkillEnablementOut,
  SsoConfigOut,
  TenantOut,
  TokenPair,
} from "./types";

// ----------------------------------------------------------------------------
// Auth
// ----------------------------------------------------------------------------

export function signup(
  tenantId: string,
  body: {
    email: string;
    password: string;
    department?: string;
    designation?: string;
    phone?: string;
    roles?: Role[];
  }
): Promise<TokenPair> {
  return apiRequest<TokenPair>("/auth/signup", {
    method: "POST",
    body,
    unauthenticated: true,
    tenantId,
  });
}

export function login(tenantId: string, email: string, password: string): Promise<TokenPair> {
  return apiRequest<TokenPair>("/auth/login", {
    method: "POST",
    body: { email, password },
    unauthenticated: true,
    tenantId,
  });
}

export function logout(refreshToken: string): Promise<void> {
  return apiRequest<void>("/auth/logout", {
    method: "POST",
    body: { refresh_token: refreshToken },
    unauthenticated: true,
  });
}

export function acceptInvite(token: string, password: string): Promise<TokenPair> {
  return apiRequest<TokenPair>("/auth/invite/accept", {
    method: "POST",
    body: { token, password },
    unauthenticated: true,
  });
}

export function createInvite(employeeId: string): Promise<{ invite_token: string; expires_in: number }> {
  return apiRequest(`/auth/invite/${employeeId}`, { method: "POST" });
}

export function getSsoConfig(): Promise<SsoConfigOut[]> {
  return apiRequest<SsoConfigOut[]>("/auth/sso/config");
}

export function updateSsoConfig(
  provider: string,
  body: { client_id: string; client_secret: string; issuer_domain?: string; hosted_domain?: string; enabled: boolean }
): Promise<SsoConfigOut> {
  return apiRequest<SsoConfigOut>(`/auth/sso/config/${provider}`, {
    method: "PUT",
    body,
  });
}

// ----------------------------------------------------------------------------
// Tenants
// ----------------------------------------------------------------------------

export function createTenant(body: {
  company_name: string;
  plan: string;
  storage_quota_bytes?: number;
  llm_config?: Record<string, unknown>;
  branding?: Record<string, unknown>;
  subscription_status?: string;
}): Promise<TenantOut> {
  return apiRequest<TenantOut>("/tenants", {
    method: "POST",
    body,
    unauthenticated: true,
  });
}

export function getTenant(tenantId: string): Promise<TenantOut> {
  return apiRequest<TenantOut>(`/tenants/${tenantId}`);
}

export function updateTenant(tenantId: string, body: Partial<TenantOut>): Promise<TenantOut> {
  return apiRequest<TenantOut>(`/tenants/${tenantId}`, { method: "PATCH", body });
}

// ----------------------------------------------------------------------------
// Employees
// ----------------------------------------------------------------------------

export function listEmployees(limit = 50, offset = 0): Promise<Employee[]> {
  return apiRequest<Employee[]>(`/employees?limit=${limit}&offset=${offset}`);
}

export function getEmployee(id: string): Promise<Employee> {
  return apiRequest<Employee>(`/employees/${id}`);
}

export function updateEmployee(id: string, body: Partial<Employee>): Promise<Employee> {
  return apiRequest<Employee>(`/employees/${id}`, { method: "PATCH", body });
}

export function deactivateEmployee(id: string): Promise<Employee> {
  return apiRequest<Employee>(`/employees/${id}/deactivate`, { method: "POST" });
}

export function reactivateEmployee(id: string): Promise<Employee> {
  return apiRequest<Employee>(`/employees/${id}/reactivate`, { method: "POST" });
}

export function createEmployee(body: {
  email: string;
  department?: string;
  designation?: string;
  manager_id?: string;
  phone?: string;
  roles?: Role[];
}): Promise<Employee> {
  return apiRequest<Employee>("/employees", { method: "POST", body });
}

// ----------------------------------------------------------------------------
// Agents
// ----------------------------------------------------------------------------

export function getAgentByEmployee(employeeId: string): Promise<Agent> {
  return apiRequest<Agent>(`/agents/by-employee/${employeeId}`);
}

export function updateAgent(agentId: string, body: Partial<Agent>): Promise<Agent> {
  return apiRequest<Agent>(`/agents/${agentId}`, { method: "PATCH", body });
}

// ----------------------------------------------------------------------------
// Chat
// ----------------------------------------------------------------------------

export function sendChatMessage(message: string): Promise<ChatResponse> {
  return apiRequest<ChatResponse>("/chat", { method: "POST", body: { message } });
}

// ----------------------------------------------------------------------------
// Memory / conversation
// ----------------------------------------------------------------------------

export function getConversation(namespace: string, limit = 200): Promise<MemoryTurn[]> {
  return apiRequest<MemoryTurn[]>(`/memory/${encodeURIComponent(namespace)}/conversation?limit=${limit}`);
}

// ----------------------------------------------------------------------------
// Knowledge
// ----------------------------------------------------------------------------

export function listDocuments(params: {
  scope?: DocumentScope;
  department?: string;
  employee_id?: string;
  limit?: number;
  offset?: number;
}): Promise<DocumentOut[]> {
  const qs = new URLSearchParams();
  if (params.scope) qs.set("scope", params.scope);
  if (params.department) qs.set("department", params.department);
  if (params.employee_id) qs.set("employee_id", params.employee_id);
  qs.set("limit", String(params.limit ?? 100));
  qs.set("offset", String(params.offset ?? 0));
  return apiRequest<DocumentOut[]>(`/documents?${qs.toString()}`);
}

export function uploadDocument(
  file: File,
  scope: DocumentScope,
  department?: string
): Promise<DocumentOut> {
  const form = new FormData();
  form.set("scope", scope);
  if (department) form.set("department", department);
  form.set("file", file);
  return apiRequest<DocumentOut>("/documents", {
    method: "POST",
    body: form,
    isFormData: true,
  });
}

export function deleteDocument(id: string): Promise<void> {
  return apiRequest<void>(`/documents/${id}`, { method: "DELETE" });
}

// ----------------------------------------------------------------------------
// Skills / connections
// ----------------------------------------------------------------------------

export function listSkills(): Promise<SkillEnablementOut[]> {
  return apiRequest<SkillEnablementOut[]>("/skills");
}

export function updateSkillEnablement(
  skillId: string,
  body: { enabled: boolean; config: Record<string, unknown> }
): Promise<SkillEnablementOut> {
  return apiRequest<SkillEnablementOut>(`/skills/${skillId}/enablement`, { method: "PUT", body });
}

export function listConnections(): Promise<ConnectionOut[]> {
  return apiRequest<ConnectionOut[]>("/connections");
}

export function disconnectSkill(skillId: string): Promise<void> {
  return apiRequest<void>(`/connections/${skillId}`, { method: "DELETE" });
}

// ----------------------------------------------------------------------------
// Analytics (direct, bypassing the gateway prefix — see brief)
// ----------------------------------------------------------------------------

function rangeQuery(fromDate?: string, toDate?: string): string {
  const qs = new URLSearchParams();
  if (fromDate) qs.set("from_date", fromDate);
  if (toDate) qs.set("to_date", toDate);
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export function getAdminAnalytics(fromDate?: string, toDate?: string): Promise<AdminAnalytics> {
  return apiRequest<AdminAnalytics>(`/analytics/admin${rangeQuery(fromDate, toDate)}`);
}

export function getFinanceAnalytics(fromDate?: string, toDate?: string): Promise<FinanceAnalytics> {
  return apiRequest<FinanceAnalytics>(`/analytics/finance${rangeQuery(fromDate, toDate)}`);
}

export function getItAnalytics(fromDate?: string, toDate?: string): Promise<ItAnalytics> {
  return apiRequest<ItAnalytics>(`/analytics/it${rangeQuery(fromDate, toDate)}`);
}

// ----------------------------------------------------------------------------
// Audit log (direct, same-origin, bypassing the gateway — see brief)
// ----------------------------------------------------------------------------

export function getAuditLogs(params: {
  action?: string;
  target_type?: string;
  actor_employee_id?: string;
  from_date?: string;
  to_date?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditLogEntryOut[]> {
  const qs = new URLSearchParams();
  if (params.action) qs.set("action", params.action);
  if (params.target_type) qs.set("target_type", params.target_type);
  if (params.actor_employee_id) qs.set("actor_employee_id", params.actor_employee_id);
  if (params.from_date) qs.set("from_date", params.from_date);
  if (params.to_date) qs.set("to_date", params.to_date);
  qs.set("limit", String(params.limit ?? 100));
  qs.set("offset", String(params.offset ?? 0));
  return apiRequest<AuditLogEntryOut[]>(`/audit-logs?${qs.toString()}`);
}
