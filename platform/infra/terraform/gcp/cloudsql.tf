# Two Cloud SQL instances, mirroring infra/k8s/postgres.yaml +
# postgres-vector.yaml's existing split: one shared instance for the eight
# services that just need plain Postgres, one dedicated instance for
# knowledge-service's pgvector requirement — same reasoning as the k8s
# manifests' comments (keep the pgvector extension's requirements, and any
# future divergence in Postgres version/collation, off the other eight
# services' instance entirely).
#
# Both are PRIVATE IP ONLY (ipv4_enabled = false) — reachable only from
# inside this VPC, via the Cloud SQL Auth Proxy sidecar every DB-backed
# pod runs (see ../../k8s/overlays/gcp). No public IP, no `0.0.0.0/0`
# authorized network, ever.

locals {
  # One logical database (and one Cloud SQL user) per service on the main
  # instance — matches infra/docker/init-db.sh's list exactly.
  main_instance_databases = [
    "tenant_service",
    "employee_service",
    "auth_service",
    "agent_registry",
    "memory_service",
    "analytics_service",
    "skill_marketplace",
    "audit_service",
  ]
}

resource "google_sql_database_instance" "main" {
  project             = var.project_id
  name                = "staffstream-main-${var.environment}"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = false

  depends_on = [google_service_networking_connection.private_service_connection]

  settings {
    tier              = var.cloud_sql_tier
    availability_type = var.cloud_sql_availability_type
    disk_autoresize   = true
    disk_type         = "PD_SSD"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.this.id
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
    }

    # Phase 10's load test (../../../docs/phase10-load-test.md) sized
    # max_connections against 8 services sharing one instance, each pod
    # pooling pool_size=10/max_overflow=15 across each service's own HPA
    # ceiling (3-6 replicas) — see that doc for the full reasoning. Same
    # number carried over here since the shape of the problem (many pods,
    # one shared instance) is identical to the in-cluster deployment.
    database_flags {
      name  = "max_connections"
      value = "300"
    }
  }
}

resource "google_sql_database" "main" {
  for_each = toset(local.main_instance_databases)
  project  = var.project_id
  name     = each.value
  instance = google_sql_database_instance.main.name
}

# One Cloud SQL user per service rather than one shared login (a step up
# from the docker-compose/local-k8s setup's single `staffstream` user,
# worth doing now that everything else here is already least-privilege by
# service). Cloud SQL Postgres users are instance-wide, not scoped to one
# database at the IAM level — each service's own DATABASE_URL simply never
# names any database but its own, same trust boundary the tenant-isolation
# ORM layer relies on at the application level. Tightening this further
# with an explicit per-database GRANT is a reasonable follow-up (would
# need the community `cyrilgdn/postgresql` Terraform provider, connecting
# through the proxy at apply time — not added here to keep this provider
# set minimal).
resource "random_password" "main_db_password" {
  for_each = toset(local.main_instance_databases)
  length   = 32
  special  = false # keep the generated password safe to embed unescaped in a postgresql+asyncpg:// URL
}

resource "google_sql_user" "main" {
  for_each = toset(local.main_instance_databases)
  project  = var.project_id
  name     = each.value
  instance = google_sql_database_instance.main.name
  password = random_password.main_db_password[each.value].result
}

# --- Dedicated pgvector instance for knowledge-service ----------------------

resource "google_sql_database_instance" "vector" {
  project             = var.project_id
  name                = "staffstream-vector-${var.environment}"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = false

  depends_on = [google_service_networking_connection.private_service_connection]

  settings {
    tier              = var.cloud_sql_tier
    availability_type = var.cloud_sql_availability_type
    disk_autoresize   = true
    disk_type         = "PD_SSD"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.this.id
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
    }

    # Only knowledge-service's own HPA ceiling (4 replicas) uses this
    # instance — see docs/phase10-load-test.md's reasoning for the
    # equivalent number on the shared instance above.
    database_flags {
      name  = "max_connections"
      value = "150"
    }
  }
}

resource "google_sql_database" "knowledge_service" {
  project  = var.project_id
  name     = "knowledge_service"
  instance = google_sql_database_instance.vector.name
}

resource "random_password" "knowledge_service_db_password" {
  length  = 32
  special = false
}

resource "google_sql_user" "knowledge_service" {
  project  = var.project_id
  name     = "knowledge_service"
  instance = google_sql_database_instance.vector.name
  password = random_password.knowledge_service_db_password.result
}

# pgvector itself (`CREATE EXTENSION vector`) is a per-database SQL
# statement, not a Cloud SQL instance flag or a resource this Google
# Terraform provider manages — run scripts/enable-pgvector.sh once after
# this instance exists (idempotent, safe to re-run). See that script and
# README.md for why this is a deliberate one-time manual/CI step rather
# than a Terraform resource.
