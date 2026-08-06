#!/usr/bin/env bash
# Runs once, automatically, the first time the postgres container starts
# against an empty data directory (docker-entrypoint-initdb.d convention —
# never re-runs against an existing /mnt/db-data, so this is safe to leave
# in place across restarts). Same pattern as
# ../docker/init-db.sh / ../k8s/base/postgres.yaml's ConfigMap, now
# covering all 9 DB-backed services this demo runs (see
# backend-compose.yml's top comment for the two non-DB limitations that
# remain — no broker, no real per-connector OAuth apps).
set -euo pipefail

for db in tenant_service employee_service auth_service agent_registry memory_service knowledge_service analytics_service audit_service skill_marketplace; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE $db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
done

# pgvector only needs to be enabled on knowledge_service's own database —
# `CREATE EXTENSION` is per-database, not instance-wide.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname knowledge_service \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
