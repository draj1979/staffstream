# Every API this config touches — enabled up front so the rest of the
# config can just `depends_on = [google_project_service.apis]` instead of
# each resource needing to know which specific API backs it.
locals {
  required_apis = [
    "compute.googleapis.com",
    "container.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "sts.googleapis.com", # Workload Identity Federation token exchange (GitHub Actions OIDC)
  ]
}

resource "google_project_service" "apis" {
  for_each                  = toset(local.required_apis)
  project                   = var.project_id
  service                   = each.value
  disable_dependent_services = false
  disable_on_destroy         = false # don't take down APIs other things in the project might also depend on
}
