#!/bin/bash
# GCE startup-script for backend-vm — see db-vm-startup.sh's header
# comment for why this is written to be safe to re-run on every boot,
# not just the first one.
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
fi

# `gcloud auth configure-docker` needs the gcloud CLI, which Debian's base
# image doesn't ship — but docker itself can pull from Artifact Registry
# using the VM's own attached service account via the standard GCE
# metadata-server credential helper once docker-credential-gcr is
# present. Simpler and with fewer moving parts for a demo: install the
# credential helper.
if ! command -v docker-credential-gcr >/dev/null 2>&1; then
  curl -fsSL "https://github.com/GoogleCloudPlatform/docker-credential-gcr/releases/download/v2.1.22/docker-credential-gcr_linux_amd64-2.1.22.tar.gz" \
    | tar xz -C /usr/local/bin docker-credential-gcr
  docker-credential-gcr configure-docker --registries=asia-south1-docker.pkg.dev
fi

mkdir -p /opt/staffstream

cat > /etc/systemd/system/staffstream-backend.service <<'EOF'
[Unit]
Description=StaffStream demo — backend-vm (app services + Caddy)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/staffstream
ExecStart=/usr/bin/docker compose -f backend-compose.yml up -d
ExecStop=/usr/bin/docker compose -f backend-compose.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable staffstream-backend.service
# Harmless no-op until backend-compose.yml/.env/Caddyfile/scripts/ are
# copied to /opt/staffstream (see README.md's setup order) — every boot
# after that first manual bring-up this starts the whole stack
# automatically, no SSH session required.
systemctl start staffstream-backend.service || true
