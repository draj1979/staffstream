#!/usr/bin/env bash
# Run ON backend-vm by .github/workflows/deploy-gcp.yml over SSH, only
# when this run's deploy (ci-deploy.sh) or the external smoke test
# fails — reverts IMAGE_TAG to the value the workflow captured before it
# changed anything and brings the stack back up on it, so a bad deploy
# never leaves the VM stuck on a half-upgraded, partially-healthy mix of
# old and new images.
set -euo pipefail

PREV_TAG="${1:?Usage: ci-rollback.sh <previous-image-tag>}"
cd /opt/staffstream

sudo sed -i "s|^IMAGE_TAG=.*|IMAGE_TAG=${PREV_TAG}|" .env
sudo docker compose -f backend-compose.yml pull
sudo docker compose -f backend-compose.yml up -d
