# Single source of truth for "which service needs which secrets" — drives
# both secrets.tf's IAM grants (least-privilege: a service only gets
# secretAccessor on secrets in its own list) and
# ../../k8s/overlays/gcp/secret-provider-classes.yaml's per-service
# SecretProviderClass (which has to list the same names by hand, since
# Kustomize/CSI YAML can't read Terraform locals — see that file's own
# comment pointing back here). Every service also gets JWT_SECRET_KEY,
# added separately below rather than repeated in each list.
#
# Derived directly from each service's own config.py (env_prefix +
# Field(alias=...) entries) — not guessed. See docs/gcp-deployment.md for
# how this was cross-checked.
locals {
  service_specific_secrets = {
    tenant-service     = ["TENANT_SERVICE_DATABASE_URL"]
    employee-service    = ["EMPLOYEE_SERVICE_DATABASE_URL"]
    auth-service         = ["AUTH_SERVICE_DATABASE_URL", "SSO_ENCRYPTION_KEY"]
    agent-registry       = ["AGENT_REGISTRY_DATABASE_URL"]
    llm-gateway = [
      "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
      "MISTRAL_API_KEY", "DEEPSEEK_API_KEY", "LLAMA_API_KEY",
    ]
    openclaw-runtime   = [] # no DB, no provider keys of its own — calls llm-gateway rather than holding LLM credentials itself
    memory-service     = ["MEMORY_SERVICE_DATABASE_URL"]
    knowledge-service  = ["KNOWLEDGE_SERVICE_DATABASE_URL", "VOYAGE_API_KEY"]
    api-gateway        = ["REDIS_URL"] # Memorystore AUTH means this is a secret now, unlike the in-cluster unauthenticated Redis
    analytics-service  = ["ANALYTICS_SERVICE_DATABASE_URL"]
    skill-marketplace = [
      "SKILL_MARKETPLACE_DATABASE_URL", "OAUTH_ENCRYPTION_KEY",
      "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET",
      "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
      "SALESFORCE_CLIENT_ID", "SALESFORCE_CLIENT_SECRET",
      "HUBSPOT_CLIENT_ID", "HUBSPOT_CLIENT_SECRET",
      "JIRA_CLIENT_ID", "JIRA_CLIENT_SECRET",
      "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET",
      "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET",
      "SERVICENOW_CLIENT_ID", "SERVICENOW_CLIENT_SECRET",
      "SAP_CLIENT_ID", "SAP_CLIENT_SECRET",
      "ORACLE_CLIENT_ID", "ORACLE_CLIENT_SECRET",
      "WHATSAPP_CLIENT_ID", "WHATSAPP_CLIENT_SECRET",
    ]
    audit-service = ["AUDIT_SERVICE_DATABASE_URL"]
  }

  # Every service that talks to another service or mints/verifies a token
  # needs this — which in practice is all twelve (see libs/auth's own
  # comment: JWT_SECRET_KEY "must be IDENTICAL across every service that
  # mints or verifies tokens").
  all_services = keys(local.service_specific_secrets)

  service_secrets = {
    for svc, secrets in local.service_specific_secrets :
    svc => concat(["JWT_SECRET_KEY"], secrets)
  }

  # The 9 services that need a Cloud SQL Auth Proxy sidecar + roles/cloudsql.client —
  # everything with its own *_DATABASE_URL above, split by which instance
  # (main vs. vector) they connect to.
  main_db_services   = ["tenant-service", "employee-service", "auth-service", "agent-registry", "memory-service", "analytics-service", "skill-marketplace", "audit-service"]
  vector_db_services  = ["knowledge-service"]
  db_backed_services = concat(local.main_db_services, local.vector_db_services)

  # Flattened, de-duplicated list of every secret id referenced above —
  # what secrets.tf actually creates `google_secret_manager_secret`
  # resources for.
  all_secret_ids = distinct(flatten([for svc, secrets in local.service_secrets : secrets]))
}
