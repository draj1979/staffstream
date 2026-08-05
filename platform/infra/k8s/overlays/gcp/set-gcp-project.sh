#!/usr/bin/env bash
# Replaces the __GCP_PROJECT_ID__ / __GCP_REGION__ / __GCP_ENVIRONMENT__
# placeholder tokens across this overlay with real values, once.
#
# Why a one-time sed pass and not a Kustomize `replacements`/envsubst
# render step at apply time: __GCP_PROJECT_ID__ appears both in plain
# scalar fields (deployment-patches.yaml's cloud-sql-proxy args, which
# Kustomize `replacements` *could* target) and inside a multi-line YAML
# string embedded in a string field (secret-provider-classes.yaml's
# `parameters.secrets`, which it can't reach into). Splitting the
# substitution mechanism by field type would be more moving parts than
# this task's actual scope justifies. A plain committed-after-substitution
# overlay is also simpler for Argo CD: it builds this directory with a
# stock `kustomize build`, no plugin or extra render step required at
# sync time — see ../../../terraform/gcp/argocd.tf.
#
# Usage (values from `terraform -chdir=../../../terraform/gcp output`,
# or your terraform.tfvars):
#   ./set-gcp-project.sh my-project us-central1 prod
set -euo pipefail

PROJECT_ID="${1:?Usage: $0 <project_id> <region> <environment>}"
REGION="${2:?Usage: $0 <project_id> <region> <environment>}"
ENVIRONMENT="${3:?Usage: $0 <project_id> <region> <environment>}"

cd "$(dirname "$0")"

# macOS/BSD sed and GNU sed disagree on -i's argument — this works on both.
sed_inplace() {
  if sed --version >/dev/null 2>&1; then
    sed -i "$@" # GNU
  else
    sed -i '' "$@" # BSD/macOS
  fi
}

for f in secret-provider-classes.yaml deployment-patches.yaml service-accounts.yaml kustomization.yaml; do
  sed_inplace \
    -e "s/__GCP_PROJECT_ID__/${PROJECT_ID}/g" \
    -e "s/__GCP_REGION__/${REGION}/g" \
    -e "s/__GCP_ENVIRONMENT__/${ENVIRONMENT}/g" \
    "${f}"
done

echo "Replaced tokens in secret-provider-classes.yaml, deployment-patches.yaml, service-accounts.yaml, and kustomization.yaml."
echo "Remaining placeholder tokens (should be none):"
grep -n '__GCP_' *.yaml || echo "  (none)"
