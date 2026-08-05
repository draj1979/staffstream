# One Docker repo for all twelve service images — matches the existing
# `staffstream/<service>:latest` naming already used by every Dockerfile
# and infra/k8s/services/*.yaml (see infra/k8s/README.md's "Images"
# section); the GCP overlay only needs to change the registry host prefix
# in front of that same name, not the naming scheme itself.
resource "google_artifact_registry_repository" "this" {
  project       = var.project_id
  location      = var.region
  repository_id = "staffstream"
  format        = "DOCKER"
  description   = "StaffStream platform service images"

  cleanup_policies {
    id     = "keep-last-20-per-service"
    action = "KEEP"
    most_recent_versions {
      keep_count = 20
    }
  }

  # `:latest` accumulates fast when every CI push overwrites it (see the
  # GitHub Actions workflow — every image is also tagged with the commit
  # SHA, which is what deployments actually pin, `:latest` is convenience
  # only) — clean up untagged/superseded layers older than 30 days so the
  # repo doesn't grow unbounded.
  cleanup_policies {
    id     = "delete-untagged-after-30d"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "2592000s" # 30 days
    }
  }

  depends_on = [google_project_service.apis]
}
