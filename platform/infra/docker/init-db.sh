#!/usr/bin/env bash
set -euo pipefail

for db in tenant_service employee_service auth_service agent_registry memory_service analytics_service; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE $db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
done
