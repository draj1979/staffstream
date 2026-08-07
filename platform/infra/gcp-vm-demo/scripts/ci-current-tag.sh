#!/usr/bin/env bash
# Run ON backend-vm by .github/workflows/deploy-gcp.yml over SSH, before
# the deploy touches anything — prints the currently-deployed IMAGE_TAG
# (or "latest" if the line isn't present in .env at all) so the workflow
# always has a real value to roll back to if this run's deploy or smoke
# test fails.
set -euo pipefail
cd /opt/staffstream
sudo grep '^IMAGE_TAG=' .env 2>/dev/null | head -1 | cut -d= -f2 || echo latest
