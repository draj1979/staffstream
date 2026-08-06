// Shared API types. Kept close to the backend's actual response shapes —
// see CLAUDE.md / the build brief for the source-of-truth contract.

export type Role = "admin" | "manager" | "employee";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type?: string;
}

export interface JwtClaims {
  sub: string;
  tenant_id: string;
  role: Role;
  exp: number;
  [key: string]: unknown;
}

export interface Employee {
  employee_id: string;
  tenant_id: string;
  department: string | null;
  designation: string | null;
  manager_id: string | null;
  phone: string | null;
  email: string;
  agent_id: string | null;
  roles: Role[];
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TenantOut {
  tenant_id: string;
  company_name: string;
  plan: string;
  storage_quota_bytes?: number | null;
  llm_config?: Record<string, unknown> | null;
  branding?: Record<string, unknown> | null;
  subscription_status?: string | null;
  [key: string]: unknown;
}

export interface Agent {
  agent_id: string;
  tenant_id: string;
  employee_id: string;
  name: string;
  personality: string | null;
  provider: string;
  model: string;
  temperature: number;
  prompt: string | null;
  memory_namespace: string;
  knowledge_sources: string[];
  skills: string[];
  permissions: string[];
  created_at: string;
  updated_at: string;
}

export interface ChatResponse {
  reply: string;
  agent_id: string;
  model: string;
  usage: {
    input_tokens: number;
    output_tokens: number;
  };
}

export interface MemoryTurn {
  id: string;
  memory_namespace: string;
  role: "user" | "assistant" | string;
  content: string;
  created_at: string;
}

export type DocumentScope = "company" | "department" | "personal";
export type DocumentStatus = "processing" | "ready" | "failed";

export interface DocumentOut {
  id: string;
  tenant_id: string;
  scope: DocumentScope;
  department: string | null;
  employee_id: string | null;
  uploaded_by_employee_id: string;
  filename: string;
  content_type: string;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export const CONNECTOR_IDS = [
  "slack",
  "google_calendar",
  "salesforce",
  "hubspot",
  "jira",
  "github",
  "microsoft_teams",
  "microsoft_365",
  "servicenow",
  "sap",
  "oracle",
  "whatsapp",
] as const;

export type ConnectorId = (typeof CONNECTOR_IDS)[number];

export const CONNECTOR_LABELS: Record<ConnectorId, string> = {
  slack: "Slack",
  google_calendar: "Google Calendar",
  salesforce: "Salesforce",
  hubspot: "HubSpot",
  jira: "Jira",
  github: "GitHub",
  microsoft_teams: "Microsoft Teams",
  microsoft_365: "Microsoft 365",
  servicenow: "ServiceNow",
  sap: "SAP",
  oracle: "Oracle",
  whatsapp: "WhatsApp",
};

export interface SkillEnablementOut {
  skill_id: string;
  name: string;
  description: string;
  connector: string;
  enabled: boolean;
  config: Record<string, unknown>;
}

export interface ConnectionOut {
  skill_id: string;
  connected: boolean;
  external_account: string | null;
  granted_scope: string | null;
  connected_at: string | null;
}

export interface SsoConfigOut {
  provider: "google_workspace" | "auth0";
  client_id: string | null;
  issuer_domain: string | null;
  hosted_domain: string | null;
  enabled: boolean;
}

export interface AdminAnalytics {
  range: { from_date: string; to_date: string } | Record<string, unknown>;
  total_conversations: number;
  success_rate: number;
  active_employees: number;
  active_agents: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
}

export interface FinanceAnalytics {
  range: Record<string, unknown>;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  cost_by_model: Array<{
    model: string;
    call_count: number;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
  }>;
  cost_by_employee: Array<{ employee_id: string; call_count: number; cost_usd: number }>;
  daily_cost: Array<{ day: string; cost_usd: number }>;
}

export interface ItAnalytics {
  range: Record<string, unknown>;
  total_requests: number;
  error_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  requests_by_agent: Array<{
    agent_id: string;
    request_count: number;
    error_count: number;
    avg_latency_ms: number;
  }>;
  errors_by_stage: Array<{ error_stage: string; count: number }>;
}

export type AuditAction =
  | "sso.config_changed"
  | "agent.updated"
  | "skill.enablement_changed"
  | "skill.connected"
  | "skill.disconnected"
  | "tenant.updated"
  | "employee.created"
  | "employee.updated"
  | "employee.role_changed"
  | "employee.deactivated"
  | "employee.reactivated";

export interface AuditLogEntryOut {
  id: string;
  actor_employee_id: string | null;
  action: AuditAction | string;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ApiErrorBody {
  detail?: string | Array<{ msg: string; loc?: (string | number)[] }>;
  error_message?: string;
  [key: string]: unknown;
}
