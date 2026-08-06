#!/bin/bash
# GCE startup-script for db-vm — runs as root on EVERY boot (that's how
# GCE metadata startup-scripts work, not just the first one), so
# everything here is written to be safe to re-run: installing Docker is
# skipped if already present, the data disk is only *formatted* if it has
# no filesystem yet (mkfs on an already-formatted disk would destroy the
# data it's the whole point of this split-disk layout to protect), and
# the fstab entry is only added once.
set -euo pipefail

# Matches ../setup.sh's DB_DISK_NAME default (db-vm-data) via GCE's
# --device-name -> /dev/disk/by-id/google-<device-name> convention — if
# you override DB_DISK_NAME there, update this to match.
DATA_DISK_DEVICE="/dev/disk/by-id/google-db-vm-data"
DATA_MOUNT="/mnt/db-data"

# --- Docker + compose plugin (idempotent) -----------------------------
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

# --- Format the attached data disk, ONLY if it has no filesystem yet ---
if ! blkid "$DATA_DISK_DEVICE" >/dev/null 2>&1; then
  echo "db-vm-startup: formatting ${DATA_DISK_DEVICE} (first boot — no filesystem found)"
  mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard "$DATA_DISK_DEVICE"
else
  echo "db-vm-startup: ${DATA_DISK_DEVICE} already has a filesystem, not reformatting"
fi

mkdir -p "$DATA_MOUNT"
if ! mountpoint -q "$DATA_MOUNT"; then
  mount -o discard,defaults "$DATA_DISK_DEVICE" "$DATA_MOUNT"
fi

# fstab entry so the mount survives a reboot without relying on this
# script re-running (belt and suspenders — it does re-run every boot, but
# this is the standard, expected mechanism).
if ! grep -q "$DATA_MOUNT" /etc/fstab; then
  DISK_UUID="$(blkid -s UUID -o value "$DATA_DISK_DEVICE")"
  echo "UUID=${DISK_UUID} ${DATA_MOUNT} ext4 discard,defaults,nofail 0 2" >> /etc/fstab
fi

mkdir -p "${DATA_MOUNT}/postgres" "${DATA_MOUNT}/redis"
# Postgres's container runs as its own non-root user (uid 999 in the
# official images) — pre-creating with permissive-enough ownership avoids
# a first-boot permission-denied failure on an empty new disk.
chown -R 999:999 "${DATA_MOUNT}/postgres"

# --- systemd unit (installed + enabled, not force-started — see
# README.md's setup order: compose.yml/.env need to be copied to
# /opt/staffstream first, which this startup-script doesn't do, since
# they carry real secrets that don't belong in instance metadata) -------
mkdir -p /opt/staffstream
cat > /etc/systemd/system/staffstream-db.service <<'EOF'
[Unit]
Description=StaffStream demo — db-vm (Postgres + Redis)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/staffstream
ExecStart=/usr/bin/docker compose -f db-compose.yml up -d
ExecStop=/usr/bin/docker compose -f db-compose.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable staffstream-db.service
# Harmless no-op if db-compose.yml/.env aren't in /opt/staffstream yet
# (first boot, before the manual scp step in README.md) — every boot
# after that first manual `docker compose up -d` this actually starts
# the stack automatically.
systemctl start staffstream-db.service || true
