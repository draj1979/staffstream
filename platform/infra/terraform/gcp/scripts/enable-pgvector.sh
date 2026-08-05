#!/usr/bin/env bash
# Enables the pgvector extension on the knowledge_service database, once,
# after `terraform apply` has created the vector Cloud SQL instance.
#
# Why this is a script and not a Terraform resource: `CREATE EXTENSION` is
# a SQL statement, not something the hashicorp/google provider exposes as
# a resource. The community `cyrilgdn/postgresql` provider can run
# arbitrary SQL like this, but it needs a live connection to the database
# at `terraform apply` time — meaning either a public IP (this instance
# deliberately has none) or the Cloud SQL Auth Proxy already running
# wherever `terraform apply` executes. Bringing in a whole extra provider
# and a proxy-in-CI dependency for one idempotent one-line statement isn't
# worth it; a script run once (or wired into the GitHub Actions workflow
# as a one-time job) is simpler and just as safe.
#
# Requires: gcloud (authenticated), the Cloud SQL Auth Proxy binary
# (https://cloud.google.com/sql/docs/postgres/sql-proxy#install), psql.
#
# Usage:
#   PROJECT_ID=my-project ./enable-pgvector.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID to your GCP project}"
REGION="${REGION:-us-central1}"
ENVIRONMENT="${ENVIRONMENT:-prod}"
INSTANCE_CONNECTION_NAME="${PROJECT_ID}:${REGION}:staffstream-vector-${ENVIRONMENT}"

DB_USER="knowledge_service"
DB_NAME="knowledge_service"
DB_PASSWORD="$(gcloud secrets versions access latest --secret=KNOWLEDGE_SERVICE_DATABASE_URL --project="${PROJECT_ID}" 2>/dev/null | sed -n 's#.*://[^:]*:\([^@]*\)@.*#\1#p')"

if [[ -z "${DB_PASSWORD}" ]]; then
  echo "Couldn't read the knowledge_service DB password from Secret Manager." >&2
  echo "Populate the KNOWLEDGE_SERVICE_DATABASE_URL secret first (see ../secrets.tf's comments and ../README.md)." >&2
  exit 1
fi

echo "Starting Cloud SQL Auth Proxy for ${INSTANCE_CONNECTION_NAME} on 127.0.0.1:5433..."
cloud-sql-proxy --port 5433 "${INSTANCE_CONNECTION_NAME}" &
PROXY_PID=$!
trap 'kill ${PROXY_PID} 2>/dev/null || true' EXIT

# Give the proxy a moment to establish its listener before psql connects.
for _ in $(seq 1 20); do
  if (echo > "/dev/tcp/127.0.0.1/5433") >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

PGPASSWORD="${DB_PASSWORD}" psql \
  --host=127.0.0.1 --port=5433 \
  --username="${DB_USER}" --dbname="${DB_NAME}" \
  --command="CREATE EXTENSION IF NOT EXISTS vector;"

echo "pgvector enabled on ${DB_NAME}@${INSTANCE_CONNECTION_NAME}."
