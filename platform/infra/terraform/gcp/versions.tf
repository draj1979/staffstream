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
  # bucket it stores its own state in). Uncomment and fill in once, or
  # pass equivalent -backend-config= flags at `terraform init` time (the
  # GitHub Actions workflow does the latter, keeping the project/bucket
  # name out of committed source — see ../../.github/workflows/deploy-gcp.yml).
  #
  # backend "gcs" {
  #   bucket = "REPLACE_ME-staffstream-tfstate"
  #   prefix = "gcp/prod"
  # }
}
