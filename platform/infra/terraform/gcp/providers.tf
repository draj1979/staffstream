provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Configured directly off the GKE cluster resource's own attributes rather
# than a `data "google_container_cluster"` lookup, so `terraform apply`
# works in one pass on a brand-new project — Terraform can see this
# provider depends on google_container_cluster.this without a separate
# data source that would require the cluster to already exist.
#
# Known limitation of this pattern (not fixable without a two-stage apply,
# and not worth one for a single-cluster setup): on a truly first-ever
# apply into an empty project, run `terraform apply -target=google_container_cluster.this`
# once before the full `terraform apply` — otherwise the kubernetes/helm
# providers may try to initialize before the cluster's credentials exist.
# Every apply after that first one is a normal single-pass `terraform apply`.
#
# The try()s below cover the opposite end of the same lifecycle: a
# `terraform destroy` that has already removed google_container_cluster.this
# (e.g. cluster destroyed before the remaining VPC/networking resources)
# would otherwise fail with "no client config" evaluating these provider
# blocks, even when no kubernetes/helm-managed resource is left in state to
# actually destroy. The fallback values are never dialed in that case.
provider "kubernetes" {
  host                   = try("https://${google_container_cluster.this.endpoint}", "https://invalid.invalid")
  cluster_ca_certificate = try(base64decode(google_container_cluster.this.master_auth[0].cluster_ca_certificate), "")
  token                  = try(data.google_client_config.default.access_token, "")
}

provider "helm" {
  kubernetes {
    host                   = try("https://${google_container_cluster.this.endpoint}", "https://invalid.invalid")
    cluster_ca_certificate = try(base64decode(google_container_cluster.this.master_auth[0].cluster_ca_certificate), "")
    token                  = try(data.google_client_config.default.access_token, "")
  }
}

data "google_client_config" "default" {}
