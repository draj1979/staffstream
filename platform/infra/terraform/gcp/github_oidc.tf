# Workload Identity Federation for GitHub Actions — lets the deploy
# workflow (../../.github/workflows/deploy-gcp.yml) authenticate to GCP
# using GitHub's own OIDC token, exchanged for short-lived GCP
# credentials. No service account key file is ever generated, stored as a
# GitHub secret, or rotated by hand — the trust relationship below is the
# entire credential.
#
# This pool ("github-actions") already existed in this project before
# StaffStream — another app here (draj1979/vitaliq-app2) already uses it
# via its own provider ("github", a different provider_id from
# "github-actions" below, so the two coexist without collision) and its
# own GSA. Imported into this state deliberately (shared, not
# StaffStream-exclusive) rather than StaffStream minting a second,
# redundant pool — see the provider block below for StaffStream's own,
# separately-scoped trust boundary within it.
resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"
  description               = "Federates GitHub Actions OIDC tokens for CI/CD — no GCP service account keys"

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions"
  display_name                       = "GitHub Actions OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # The actual security boundary: only a workflow run FROM this exact
  # repo, on this exact ref (var.github_deploy_ref — a push to main by
  # default, not an arbitrary PR from a fork), can exchange a token
  # through this provider at all. Scoping this at the provider level (not
  # just the downstream IAM binding) means a token that fails this
  # condition is rejected during the OIDC exchange itself, never even
  # reaching the point of trying to impersonate a GCP identity.
  attribute_condition = "assertion.repository == \"${var.github_repository}\" && assertion.ref == \"${var.github_deploy_ref}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# The identity GitHub Actions actually runs as — deliberately narrow:
# push images to this one Artifact Registry repo, nothing else. It does
# NOT get Secret Manager access (that's each service's own GSA, see
# workload_identity.tf) and does NOT get direct GKE/cluster access — the
# deploy step commits an updated image tag back to this git repo instead,
# and Argo CD (running in-cluster, watching that path) is what actually
# applies it. That split means a compromised CI run can push a bad image
# and open a PR/commit, but can't directly mutate live cluster state,
# read any application secret, or bypass Argo CD's own sync/diff view.
resource "google_service_account" "github_deployer" {
  project      = var.project_id
  account_id   = "github-actions-deployer"
  display_name = "GitHub Actions CI/CD (Workload Identity Federation)"
}

resource "google_service_account_iam_member" "github_deployer_wif_binding" {
  service_account_id = google_service_account.github_deployer.name
  role                = "roles/iam.workloadIdentityUser"
  member              = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

resource "google_artifact_registry_repository_iam_member" "github_deployer_push" {
  project    = var.project_id
  location   = google_artifact_registry_repository.this.location
  repository = google_artifact_registry_repository.this.repository_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.github_deployer.email}"
}
