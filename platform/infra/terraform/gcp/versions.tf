terraform {
  required_version = ">= 1.7"

  required_providers {
    google      = { source = "hashicorp/google", version = "~> 5.30" }
    google-beta = { source = "hashicorp/google-beta", version = "~> 5.30" }
    kubernetes  = { source = "hashicorp/kubernetes", version = "~> 2.31" }
    helm        = { source = "hashicorp/helm", version = "~> 2.14" }
    random      = { source = "hashicorp/random", version = "~> 3.6" }
  }

  # GCS backend — bucket must already exist (Terraform can't create the
  # bucket it stores its own state in). bucket/prefix are supplied via
  # `-backend-config=` at `terraform init` time (kept out of this
  # committed file so it stays project-agnostic — see
  # ../../.github/workflows/deploy-gcp.yml for the CI equivalent of the
  # init command run for this deployment).
  backend "gcs" {}
}
