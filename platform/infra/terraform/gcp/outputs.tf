output "gke_cluster_name" {
  value = google_container_cluster.this.name
}

output "gke_cluster_endpoint" {
  value     = google_container_cluster.this.endpoint
  sensitive = true
}

output "gke_get_credentials_command" {
  description = "Run this to point kubectl at the new cluster."
  value       = "gcloud container clusters get-credentials ${google_container_cluster.this.name} --region ${var.region} --project ${var.project_id}"
}

output "artifact_registry_repository_url" {
  description = "Prefix every service image is pushed under, e.g. <this>/tenant-service:<sha> — used by the GitHub Actions deploy workflow and by ../k8s/overlays/gcp's image references."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.this.repository_id}"
}

output "cloud_sql_main_connection_name" {
  description = "INSTANCE_CONNECTION_NAME for the Cloud SQL Auth Proxy sidecar on the 8 services sharing the main instance."
  value       = google_sql_database_instance.main.connection_name
}

output "cloud_sql_vector_connection_name" {
  description = "INSTANCE_CONNECTION_NAME for the Cloud SQL Auth Proxy sidecar on knowledge-service (the pgvector instance)."
  value       = google_sql_database_instance.vector.connection_name
}

output "redis_host" {
  value = google_redis_instance.this.host
}

output "service_account_emails" {
  description = "Each backend service's GSA email — the value ../k8s/overlays/gcp/service-accounts.yaml's KSAs must have in their iam.gke.io/gcp-service-account annotation for Workload Identity to actually bind."
  value       = { for svc, sa in google_service_account.service : svc => sa.email }
}

output "github_actions_workload_identity_provider" {
  description = "Full resource name for the WIF provider — this is the `workload_identity_provider` input the GitHub Actions workflow's google-github-actions/auth step needs."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "github_actions_service_account_email" {
  description = "The `service_account` input for google-github-actions/auth in the deploy workflow."
  value       = google_service_account.github_deployer.email
}

output "manual_secrets_to_populate" {
  description = "Secret Manager secrets Terraform created with a placeholder value only — populate real values with `gcloud secrets versions add <name> --project=$PROJECT_ID --data-file=-` before the services that need them will actually work (they'll still start and serve traffic; calls needing that credential fail with a normal auth error until it's set, same as local dev — see secrets.tf's comment)."
  value       = local.manual_secret_ids
}
