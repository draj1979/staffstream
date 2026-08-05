variable "project_id" {
  description = "GCP project to deploy into. Must already exist with billing enabled."
  type        = string
}

variable "region" {
  description = "Primary region for every regional resource (GKE Autopilot, Cloud SQL, Memorystore, Artifact Registry)."
  type        = string
  default     = "asia-south1"
}

variable "environment" {
  description = "Short environment name, used as a suffix on resource names (e.g. \"prod\", \"staging\") so this config is safe to apply more than once into the same project."
  type        = string
  default     = "prod"
}

variable "k8s_namespace" {
  description = "Namespace the platform's Kubernetes manifests deploy into — must match infra/k8s/namespace.yaml (\"staffstream\")."
  type        = string
  default     = "staffstream"
}

variable "cluster_name" {
  description = "GKE Autopilot cluster name."
  type        = string
  default     = "staffstream"
}

variable "github_repository" {
  description = "GitHub repo allowed to assume the CI deployer identity via Workload Identity Federation, as \"owner/repo\" (e.g. \"draj1979/staffstream\"). The WIF attribute condition is scoped to exactly this repo — no other repo, fork, or PR from outside it can authenticate as this identity."
  type        = string
}

variable "github_deploy_ref" {
  description = "Git ref allowed to deploy (push events only, not arbitrary PRs) — e.g. \"refs/heads/main\". Tightening this beyond \"any ref in the repo\" is deliberate: a compromised feature branch's workflow shouldn't be able to push images or trigger a deploy."
  type        = string
  default     = "refs/heads/main"
}

variable "install_argocd" {
  description = "Install Argo CD into the cluster via Helm and bootstrap the root Application pointing at infra/k8s/overlays/gcp. Off by default so a first `terraform apply` doesn't assume the GKE cluster (and its Workload Identity/CSI setup) is already reachable/ready — flip on once the cluster's up and you're ready to hand off deploys to Argo CD."
  type        = bool
  default     = false
}

variable "argocd_namespace" {
  description = "Namespace Argo CD itself runs in — deliberately separate from k8s_namespace (staffstream), since Argo CD manages that namespace's contents, not the other way around."
  type        = string
  default     = "argocd"
}

variable "argocd_git_repo_url" {
  description = "Git URL Argo CD's root Application tracks (this repo). Only used when install_argocd is true."
  type        = string
  default     = "https://github.com/draj1979/staffstream.git"
}

variable "cloud_sql_tier" {
  description = "Machine tier for both Cloud SQL instances (main + vector). db-custom-2-7680 is 2 vCPU / 7.5GB — a reasonable floor for a multi-tenant platform; db-f1-micro is not offered on Postgres. Bump per real load, informed by docs/phase10-load-test.md's connection-pool numbers."
  type        = string
  default     = "db-custom-2-7680"
}

variable "cloud_sql_availability_type" {
  description = "REGIONAL for an HA standby in a second zone (recommended for anything beyond a demo), ZONAL to halve cost for a dev/staging environment."
  type        = string
  default     = "REGIONAL"
}

variable "redis_memory_size_gb" {
  description = "Memorystore Redis instance size in GB. 1GB is a reasonable floor — this backs the API Gateway's per-tenant rate limiter, a small hot working set, not a cache for bulk data."
  type        = number
  default     = 1
}

variable "redis_tier" {
  description = "STANDARD_HA for a cross-zone replica (recommended — losing Redis means every tenant loses rate limiting, not just degraded performance), BASIC to halve cost for dev/staging."
  type        = string
  default     = "STANDARD_HA"
}

# ---------------------------------------------------------------------------
# Deliberately NOT a variable: secret *values*. Terraform creates the empty
# Secret Manager secret resources (see secrets.tf) so IAM bindings and the
# CSI SecretProviderClasses have something to point at, but populating real
# values happens out-of-band (`gcloud secrets versions add`, or a dedicated
# secrets-rotation pipeline) — never through a .tfvars file, which would put
# every credential in this repo's Terraform state and in plaintext on
# whoever's disk ran `terraform apply`. See CLAUDE.md's security baseline
# ("Secrets in Vault / GCP Secret Manager ... never in env files committed
# to git") — a .tfvars file checked into git is exactly that anti-pattern
# with extra steps.
# ---------------------------------------------------------------------------
