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

# The identity GitHub Actions actually runs as. Originally scoped to
# "push images, nothing else" for the GKE/Argo CD path (a deploy was a
# git commit updating an image tag, which Argo CD — not this SA — applied
# to the cluster; see docs/gcp-deployment.md for that path if it's ever
# stood back up). Now that ../gcp-vm-demo/deploy-gcp.yml deploys straight
# to backend-vm over SSH, this SA ALSO holds roles/iap.tunnelResourceAccessor
# (project-level) and an instance-scoped roles/compute.osAdminLogin on
# backend-vm — granted by ../gcp-vm-demo/setup.sh, not here, since that
# whole two-VM path is deliberately outside this Terraform state (see
# that directory's own README for why).
#
# ⚠️ Drift warning: this SA (and its two child resources below) were
# destroyed by a `terraform destroy` run during the GKE teardown — only
# the Artifact Registry repo, this SA's push binding on it, and the WIF
# pool/provider were `terraform state rm`'d out ahead of time to protect
# them; the SA itself and its WIF trust binding were not, and got swept
# up. It was recreated directly via gcloud (see that incident's chat
# history) and is NOT currently tracked in this Terraform state — running
# `terraform state list` will not show it. A bare `terraform plan`/`apply`
# here is unsafe regardless (the full GKE/Cloud SQL/Memorystore stack is
# still defined in this directory's other .tf files, just removed from
# state — a bare apply would try to recreate all of it), so re-importing
# this SA needs to happen alongside deliberately handling that, not as a
# quick follow-up.
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
