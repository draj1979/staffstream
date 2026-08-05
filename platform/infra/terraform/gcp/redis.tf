# Memorystore for Redis, private IP inside the same VPC — backs the API
# Gateway's per-tenant rate limiter (see services/api-gateway/src/api_gateway/rate_limit.py:
# a Redis-backed fixed-window counter, deliberately not in-process, so it's
# shared and correct across every API Gateway replica/pod, same reasoning
# that made this worth a managed instance rather than an in-cluster
# StatefulSet).
resource "google_redis_instance" "this" {
  project        = var.project_id
  name           = "staffstream-${var.environment}"
  region         = var.region
  tier           = var.redis_tier
  memory_size_gb = var.redis_memory_size_gb
  redis_version  = "REDIS_7_2"

  authorized_network      = google_compute_network.this.id
  connect_mode            = "PRIVATE_SERVICE_ACCESS"
  transit_encryption_mode = "SERVER_AUTHENTICATION"

  # AUTH enabled — this is exactly why REDIS_URL is a Secret Manager
  # secret (see secrets.tf) rather than the plain ConfigMap value it is in
  # the local/docker-compose deployment, where Redis has no auth at all.
  auth_enabled = true

  depends_on = [google_service_networking_connection.private_service_connection]
}
