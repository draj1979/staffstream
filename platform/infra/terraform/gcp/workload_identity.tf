# One Google Service Account per backend service (matches CLAUDE.md's "one
# service, one directory, one clear ownership boundary" applied to IAM,
# not just code) — each bound to that same service's Kubernetes Service
# Account via Workload Identity, so a pod authenticates to GCP APIs
# (Secret Manager, Cloud SQL) as *this specific service's* identity, with
# no service account key file anywhere in the cluster or in CI (the
# GitHub Actions deploy identity is separate — see github_oidc.tf — and
# has no access to any of these secrets at all, only Artifact Registry
# push).
resource "google_service_account" "service" {
  for_each     = toset(local.all_services)
  project      = var.project_id
  account_id   = "${each.value}-sa"
  display_name = "StaffStream ${each.value} (Workload Identity)"
}

# Binds each GSA to its matching Kubernetes Service Account — the KSA
# itself is created in ../k8s/overlays/gcp/service-accounts.yaml with the
# `iam.gke.io/gcp-service-account: <this GSA's email>` annotation; this is
# the other half of that pairing, granted from the GCP side.
resource "google_service_account_iam_member" "workload_identity_binding" {
  for_each           = toset(local.all_services)
  service_account_id = google_service_account.service[each.value].name
  role                = "roles/iam.workloadIdentityUser"
  member              = "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/${each.value}-ksa]"
}

# Least-privilege Secret Manager access: a service's GSA can read exactly
# the secrets locals.tf's service_secrets map says that service needs —
# not the whole project's secrets, not even every *_DATABASE_URL, just its
# own. This is the actual enforcement point; the SecretProviderClass YAML
# in ../k8s/overlays/gcp merely lists what to *try* to mount — IAM is what
# would actually stop a compromised pod from reading another service's
# secrets even if someone misconfigured its SecretProviderClass to ask.
resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each = {
    for pair in flatten([
      for svc, secrets in local.service_secrets : [
        for secret_id in secrets : { svc = svc, secret_id = secret_id }
      ]
    ]) : "${pair.svc}.${pair.secret_id}" => pair
  }

  project   = var.project_id
  secret_id = google_secret_manager_secret.this[each.value.secret_id].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.service[each.value.svc].email}"
}

# roles/cloudsql.client — required by the Cloud SQL Auth Proxy sidecar
# (../k8s/overlays/gcp) to open a connection at all, on top of the actual
# database password each service's DATABASE_URL secret carries. Only
# granted to the 9 services that run the proxy sidecar in the first place.
resource "google_project_iam_member" "cloudsql_client" {
  for_each = toset(local.db_backed_services)
  project  = var.project_id
  role     = "roles/cloudsql.client"
  member   = "serviceAccount:${google_service_account.service[each.value].email}"
}
