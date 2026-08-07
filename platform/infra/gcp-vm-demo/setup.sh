#!/usr/bin/env bash
# Provisions the two-VM demo: a dedicated VPC, a firewall policy scoped to
# exactly what's needed (public 80/443 to backend-vm, backend-vm ->
# db-vm on 5432/6379 only, SSH only via IAP — never an open 0.0.0.0/0:22),
# a separate persistent disk for db-vm's actual data, and the two VMs
# themselves. Each `gcloud ... create` below is guarded so re-running
# this script after a partial failure doesn't error on "already exists"
# — safe to re-run end to end.
#
# This is a DEMO deployment path, deliberately simpler than
# ../terraform/gcp (GKE Autopilot + Cloud SQL + Memorystore + Workload
# Identity) — two VMs and docker compose instead of a managed cluster and
# managed databases. Good for a live demo or a cost-conscious proof of
# concept; the GKE path is what you'd actually run in production (HPA,
# per-service least-privilege IAM, managed backups, no SSH surface at
# all). See ../../docs/gcp-deployment.md for that path.
set -euo pipefail

# --- Configuration — override any of these as env vars before running ---
PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID to your GCP project}"
REGION="${REGION:-asia-south1}"
# asia-south1-a hit a real, hours-long e2-family capacity exhaustion in
# production use (every e2 size failed with resource_availability, not
# just db-vm's e2-medium) — -b is the current default for that reason,
# not a permanent guarantee either. If you hit the same error, probe for
# a zone with actual capacity before switching (a throwaway
# `gcloud compute instances create` in a candidate zone, then delete it)
# rather than assuming any specific zone is safe.
ZONE="${ZONE:-asia-south1-b}"
NETWORK_NAME="${NETWORK_NAME:-staffstream-demo}"
SUBNET_NAME="${SUBNET_NAME:-staffstream-demo}"
SUBNET_RANGE="${SUBNET_RANGE:-10.20.0.0/24}"

DB_VM_NAME="${DB_VM_NAME:-db-vm}"
DB_VM_MACHINE_TYPE="${DB_VM_MACHINE_TYPE:-e2-medium}"
# If you override this, also update the hardcoded
# /dev/disk/by-id/google-db-vm-data path in scripts/db-vm-startup.sh —
# GCE's by-id device path is derived from --device-name below, which
# defaults to matching this same value; the startup-script doesn't read
# it from metadata, so the two need to be kept in sync by hand for this
# demo script rather than fully parameterized.
DB_DISK_NAME="${DB_DISK_NAME:-db-vm-data}"
DB_DISK_SIZE_GB="${DB_DISK_SIZE_GB:-50}"

BACKEND_VM_NAME="${BACKEND_VM_NAME:-backend-vm}"
BACKEND_VM_MACHINE_TYPE="${BACKEND_VM_MACHINE_TYPE:-e2-standard-2}"
BACKEND_STATIC_IP_NAME="${BACKEND_STATIC_IP_NAME:-backend-vm-ip}"

IMAGE_FAMILY="debian-12"
IMAGE_PROJECT="debian-cloud"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

gcloud config set project "$PROJECT_ID" >/dev/null

echo "==> Enabling required APIs"
gcloud services enable compute.googleapis.com --project="$PROJECT_ID"

# --- Network -------------------------------------------------------------
echo "==> VPC + subnet"
if ! gcloud compute networks describe "$NETWORK_NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute networks create "$NETWORK_NAME" \
    --project="$PROJECT_ID" --subnet-mode=custom
fi
if ! gcloud compute networks subnets describe "$SUBNET_NAME" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute networks subnets create "$SUBNET_NAME" \
    --project="$PROJECT_ID" --network="$NETWORK_NAME" --region="$REGION" \
    --range="$SUBNET_RANGE"
fi

# Cloud Router + NAT — db-vm is intentionally --no-address (no external
# IP, see below), which also means no route to the internet at all
# without this: its startup-script needs to apt-get/curl the Docker
# install, and pull the postgres/redis images from Docker Hub, none of
# which resolve without NAT. backend-vm has its own external IP and
# doesn't strictly need this, but routes through it too for consistency
# now that it exists.
ROUTER_NAME="${NETWORK_NAME}-router"
NAT_NAME="${NETWORK_NAME}-nat"
if ! gcloud compute routers describe "$ROUTER_NAME" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute routers create "$ROUTER_NAME" \
    --project="$PROJECT_ID" --network="$NETWORK_NAME" --region="$REGION"
fi
if ! gcloud compute routers nats describe "$NAT_NAME" --router="$ROUTER_NAME" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute routers nats create "$NAT_NAME" \
    --project="$PROJECT_ID" --router="$ROUTER_NAME" --region="$REGION" \
    --nat-all-subnet-ip-ranges --auto-allocate-nat-external-ips
fi

# --- Firewall — deliberately narrow, this is the actual security boundary ---
echo "==> Firewall rules"
# SSH only via Identity-Aware Proxy's fixed source range — never a public
# 0.0.0.0/0:22. `gcloud compute ssh` automatically tunnels through IAP
# when this rule is in place and you have roles/iap.tunnelResourceAccessor.
if ! gcloud compute firewall-rules describe allow-iap-ssh --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute firewall-rules create allow-iap-ssh \
    --project="$PROJECT_ID" --network="$NETWORK_NAME" \
    --direction=INGRESS --action=ALLOW --rules=tcp:22 \
    --source-ranges=35.235.240.0/20
fi

# Public HTTP/HTTPS to backend-vm only (Caddy's ACME HTTP-01 challenge
# needs 80 reachable too, not just 443).
if ! gcloud compute firewall-rules describe allow-public-web --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute firewall-rules create allow-public-web \
    --project="$PROJECT_ID" --network="$NETWORK_NAME" \
    --direction=INGRESS --action=ALLOW --rules=tcp:80,tcp:443 \
    --source-ranges=0.0.0.0/0 --target-tags=staffstream-backend
fi

# backend-vm -> db-vm on Postgres/Redis ONLY — scoped by network tag, not
# by IP range, so it holds even if either VM's internal IP ever changes.
# db-vm has no external IP at all (--no-address below), so this is the
# only path anything can reach it by.
if ! gcloud compute firewall-rules describe allow-backend-to-db --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute firewall-rules create allow-backend-to-db \
    --project="$PROJECT_ID" --network="$NETWORK_NAME" \
    --direction=INGRESS --action=ALLOW --rules=tcp:5432,tcp:6379 \
    --source-tags=staffstream-backend --target-tags=staffstream-db
fi

# --- Service account for backend-vm (Artifact Registry pull only) -----
BACKEND_SA_NAME="staffstream-demo-backend"
BACKEND_SA_EMAIL="${BACKEND_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
echo "==> Service account for backend-vm (Artifact Registry read-only)"
if ! gcloud iam service-accounts describe "$BACKEND_SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$BACKEND_SA_NAME" \
    --project="$PROJECT_ID" \
    --display-name="StaffStream demo backend-vm (Artifact Registry pull only)"
fi
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BACKEND_SA_EMAIL}" \
  --role="roles/artifactregistry.reader" \
  --condition=None >/dev/null

# --- db-vm's separate data disk ----------------------------------------
echo "==> db-vm data disk"
if ! gcloud compute disks describe "$DB_DISK_NAME" --zone="$ZONE" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute disks create "$DB_DISK_NAME" \
    --project="$PROJECT_ID" --zone="$ZONE" \
    --size="${DB_DISK_SIZE_GB}GB" --type=pd-balanced
fi

# --- db-vm — internal only, no external IP ------------------------------
echo "==> db-vm"
if ! gcloud compute instances describe "$DB_VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute instances create "$DB_VM_NAME" \
    --project="$PROJECT_ID" --zone="$ZONE" \
    --machine-type="$DB_VM_MACHINE_TYPE" \
    --image-family="$IMAGE_FAMILY" --image-project="$IMAGE_PROJECT" \
    --network="$NETWORK_NAME" --subnet="$SUBNET_NAME" \
    --no-address \
    --tags=staffstream-db \
    --disk="name=${DB_DISK_NAME},device-name=${DB_DISK_NAME},mode=rw" \
    --metadata-from-file=startup-script="${SCRIPT_DIR}/scripts/db-vm-startup.sh" \
    --boot-disk-size=20GB
fi

DB_VM_INTERNAL_IP="$(gcloud compute instances describe "$DB_VM_NAME" \
  --zone="$ZONE" --project="$PROJECT_ID" \
  --format='get(networkInterfaces[0].networkIP)')"
echo "    db-vm internal IP: ${DB_VM_INTERNAL_IP}  (put this in backend.env's DB_VM_INTERNAL_IP)"

# --- backend-vm — public, static external IP ----------------------------
echo "==> backend-vm static external IP"
if ! gcloud compute addresses describe "$BACKEND_STATIC_IP_NAME" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute addresses create "$BACKEND_STATIC_IP_NAME" \
    --project="$PROJECT_ID" --region="$REGION"
fi
BACKEND_STATIC_IP="$(gcloud compute addresses describe "$BACKEND_STATIC_IP_NAME" \
  --region="$REGION" --project="$PROJECT_ID" --format='get(address)')"
echo "    backend-vm static IP: ${BACKEND_STATIC_IP}  (point DEMO_DOMAIN's DNS A record at this)"

echo "==> backend-vm"
if ! gcloud compute instances describe "$BACKEND_VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute instances create "$BACKEND_VM_NAME" \
    --project="$PROJECT_ID" --zone="$ZONE" \
    --machine-type="$BACKEND_VM_MACHINE_TYPE" \
    --image-family="$IMAGE_FAMILY" --image-project="$IMAGE_PROJECT" \
    --network="$NETWORK_NAME" --subnet="$SUBNET_NAME" \
    --address="$BACKEND_STATIC_IP" \
    --tags=staffstream-backend \
    --service-account="$BACKEND_SA_EMAIL" \
    --scopes=cloud-platform \
    --metadata=enable-oslogin=TRUE \
    --metadata-from-file=startup-script="${SCRIPT_DIR}/scripts/backend-vm-startup.sh" \
    --boot-disk-size=20GB
fi

# --- CI/CD SSH access — ../../.github/workflows/deploy-gcp.yml needs to
# SSH into backend-vm over IAP as the same identity it already pushes
# images as. OS Login (enabled above) ties SSH identity to IAM instead of
# instance metadata SSH keys; these two roles are what actually grant
# it, scoped to just this one instance rather than every VM in the
# project. Safe to re-run — add-iam-policy-binding is naturally
# idempotent (re-granting a role you already have is a no-op).
CI_DEPLOYER_SA_EMAIL="${CI_DEPLOYER_SA_EMAIL:-github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com}"
echo "==> CI/CD SSH access for ${CI_DEPLOYER_SA_EMAIL}"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CI_DEPLOYER_SA_EMAIL}" \
  --role="roles/iap.tunnelResourceAccessor" --condition=None >/dev/null
gcloud compute instances add-iam-policy-binding "$BACKEND_VM_NAME" \
  --zone="$ZONE" --project="$PROJECT_ID" \
  --member="serviceAccount:${CI_DEPLOYER_SA_EMAIL}" \
  --role="roles/compute.osAdminLogin" >/dev/null

cat <<EOF

==> Done. Next steps (see README.md for the full walkthrough):

1. Point DEMO_DOMAIN's DNS A record at: ${BACKEND_STATIC_IP}

2. Copy the demo config to each VM (real secrets — never committed):
   cp db.env.example db.env          # fill in real values
   cp backend.env.example backend.env  # fill in real values, including:
     DB_VM_INTERNAL_IP=${DB_VM_INTERNAL_IP}

   gcloud compute scp --zone=${ZONE} --tunnel-through-iap \\
     db-compose.yml init-db.sh db.env ${DB_VM_NAME}:/opt/staffstream/

   gcloud compute scp --zone=${ZONE} --tunnel-through-iap --recurse \\
     backend-compose.yml Caddyfile scripts backend.env ${BACKEND_VM_NAME}:/opt/staffstream/

3. SSH in (via IAP, no public SSH exposure) and bring each stack up the
   first time — after this, systemd (already installed by the
   startup-scripts above) keeps it running across reboots automatically:

   gcloud compute ssh ${DB_VM_NAME} --zone=${ZONE} --tunnel-through-iap -- \\
     'cd /opt/staffstream && mv db.env .env && sudo systemctl restart staffstream-db.service'

   gcloud compute ssh ${BACKEND_VM_NAME} --zone=${ZONE} --tunnel-through-iap -- \\
     'cd /opt/staffstream && mv backend.env .env && sudo systemctl restart staffstream-backend.service'
EOF
