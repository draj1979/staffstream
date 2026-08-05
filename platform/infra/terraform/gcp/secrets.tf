# One Secret Manager secret per env var name in locals.tf's
# service_secrets map — this is what the CSI SecretProviderClasses in
# ../k8s/overlays/gcp/secret-provider-classes.yaml mount from, replacing
# the flat staffstream-secrets Kubernetes Secret the local/docker-compose
# deployment still uses (see infra/k8s/secret.example.yaml).
#
# Two of these ("ANTHROPIC_API_KEY", "VOYAGE_API_KEY") already existed in
# this project before StaffStream, owned by another app sharing this
# project, and were imported into this state deliberately — see the
# shared_preexisting_secret_ids local below for why they're excluded from
# placeholder-version creation.
resource "google_secret_manager_secret" "this" {
  for_each  = toset(local.all_secret_ids)
  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# --- Values Terraform actually knows ---------------------------------------
#
# The *_DATABASE_URL and REDIS_URL secrets are wholly Terraform-derived (a
# generated password plus a Cloud SQL/Memorystore attribute this config
# already computed) — writing their first version here is strictly better
# than a manual `gcloud secrets versions add` step for a value a human
# would just be copy-pasting out of `terraform output` anyway. Every other
# secret below (API keys, OAuth client credentials, the two Fernet
# encryption keys, JWT_SECRET_KEY) is a real external credential Terraform
# has no business generating or knowing — see variables.tf's comment for
# why those are never a .tfvars value.
#
# Every DATABASE_URL below points at 127.0.0.1:5432 — the Cloud SQL Auth
# Proxy sidecar each DB-backed pod runs (see ../k8s/overlays/gcp), never
# the instance's private IP directly. The proxy is what actually resolves
# to that private IP, authenticated via the pod's own Workload Identity
# (roles/cloudsql.client, granted in workload_identity.tf) — no password
# needed for THAT hop, only for the proxy-to-Postgres hop the URL encodes.
locals {
  main_db_url_secrets = {
    for svc, db in zipmap(
      ["tenant-service", "employee-service", "auth-service", "agent-registry", "memory-service", "analytics-service", "skill-marketplace", "audit-service"],
      local.main_instance_databases
    ) :
    "${upper(replace(svc, "-", "_"))}_DATABASE_URL" =>
    "postgresql+asyncpg://${google_sql_user.main[db].name}:${random_password.main_db_password[db].result}@127.0.0.1:5432/${db}"
  }

  knowledge_service_db_url_secret = {
    "KNOWLEDGE_SERVICE_DATABASE_URL" = "postgresql+asyncpg://${google_sql_user.knowledge_service.name}:${random_password.knowledge_service_db_password.result}@127.0.0.1:5432/knowledge_service"
  }

  # SERVER_AUTHENTICATION (transit_encryption_mode, see redis.tf) means
  # this has to be rediss:// (TLS), not redis://. redis-py (what
  # api-gateway's rate limiter uses) supports the rediss:// scheme in
  # from_url() out of the box; if Memorystore's CA isn't in the pod's
  # trust store this may need ssl_cert_reqs tuning in
  # services/api-gateway's Redis client construction — flagged here
  # rather than assumed to just work, since it's untested against a real
  # Memorystore instance in this environment.
  redis_url_secret = {
    "REDIS_URL" = "rediss://:${google_redis_instance.this.auth_string}@${google_redis_instance.this.host}:${google_redis_instance.this.port}/0"
  }

  terraform_known_secret_values = merge(
    local.main_db_url_secrets,
    local.knowledge_service_db_url_secret,
    local.redis_url_secret,
  )

  # ANTHROPIC_API_KEY and VOYAGE_API_KEY: this project already had secrets
  # under these exact names before this config ever ran (another app in
  # the same project, sharing this project rather than a dedicated one —
  # see the import block below), each already carrying real, in-use
  # versions. Writing a placeholder version here would become the new
  # "latest" and break that other app's next pod restart/CSI remount — so
  # these two are deliberately excluded from placeholder creation
  # entirely. StaffStream's llm-gateway/knowledge-service read whatever
  # "latest" already is, i.e. they share that other app's real key. If
  # that's ever not the intent, the fix is to stop sharing (re-point these
  # two at StaffStream-only secret ids) rather than to re-add them here.
  shared_preexisting_secret_ids = ["ANTHROPIC_API_KEY", "VOYAGE_API_KEY"]

  # Everything else: created with a placeholder first version so the
  # cluster is fully bootable (every SecretProviderClass has *something*
  # to mount — see that file's comment on why an empty/missing secret
  # blocks pod startup entirely, unlike local dev's graceful degradation)
  # immediately after `terraform apply`, before anyone's populated real
  # values yet. Swap in the real value with:
  #   gcloud secrets versions add SLACK_CLIENT_ID --project=$PROJECT_ID --data-file=-
  # then restart the owning pod(s) to pick it up (CSI driver reads
  # "latest" at mount time, not continuously).
  manual_secret_ids = [
    for id in local.all_secret_ids : id
    if !contains(keys(local.terraform_known_secret_values), id)
    && !contains(local.shared_preexisting_secret_ids, id)
  ]
}

resource "google_secret_manager_secret_version" "terraform_known" {
  for_each    = local.terraform_known_secret_values
  secret      = google_secret_manager_secret.this[each.key].id
  secret_data = each.value
}

resource "google_secret_manager_secret_version" "placeholder" {
  for_each    = toset(local.manual_secret_ids)
  secret      = google_secret_manager_secret.this[each.value].id
  secret_data = "REPLACE_ME_gcloud_secrets_versions_add_${each.value}"

  # `gcloud secrets versions add` creates a brand new version (version 2,
  # 3, ...) rather than editing this one — the CSI driver reads "latest"
  # by default, so a real value added later is what actually gets mounted
  # without this Terraform resource needing to change at all. This
  # resource's only job is making sure version 1 (the placeholder) exists
  # so the cluster is bootable before that happens.
}
