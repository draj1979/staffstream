#!/usr/bin/env bash
# Run ON backend-vm by .github/workflows/deploy-gcp.yml over SSH — not
# meant to be run by hand. Bumps /opt/staffstream/.env's IMAGE_TAG to
# $1, pulls, brings the stack up, then waits (bounded, ~5 minutes) for
# every service to report healthy.
#
# Deliberately does NOT roll back on its own failure — that's
# ci-rollback.sh's job, invoked separately by the workflow only after
# this script's failure (or the external smoke test's) is confirmed, so
# the previous-tag capture the workflow already did stays the single
# source of truth for what "roll back" means.
set -euo pipefail

NEW_TAG="${1:?Usage: ci-deploy.sh <image-tag>}"
cd /opt/staffstream

if grep -q '^IMAGE_TAG=' .env; then
  sudo sed -i "s|^IMAGE_TAG=.*|IMAGE_TAG=${NEW_TAG}|" .env
else
  echo "IMAGE_TAG=${NEW_TAG}" | sudo tee -a .env >/dev/null
fi

sudo docker compose -f backend-compose.yml pull
sudo docker compose -f backend-compose.yml up -d

echo "waiting for all services to report healthy..."
for _ in $(seq 1 30); do
  # Only the failure/pending states block the wait — a service with no
  # healthcheck at all reports an empty Health column, not "unhealthy",
  # and must not be treated as a failure.
  PENDING=$(sudo docker compose -f backend-compose.yml ps --format '{{.Service}} {{.Health}}' \
    | awk '$2=="unhealthy" || $2=="starting" {print $1}')
  if [ -z "$PENDING" ]; then
    echo "all services healthy"
    exit 0
  fi
  sleep 10
done

echo "timed out waiting for services to become healthy:"
sudo docker compose -f backend-compose.yml ps
exit 1
