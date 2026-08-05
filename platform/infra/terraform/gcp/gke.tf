# GKE Autopilot: Google manages node provisioning/sizing/patching, we only
# declare the cluster shape. Workload Identity is mandatory and always-on
# for Autopilot (can't be disabled) — the workload_identity_config block
# below is declared anyway for the same reason CLAUDE.md asks for explicit
# tenant_id filters even where a shortcut exists: it's the one place
# someone reading this file finds out Workload Identity is how every pod
# authenticates to GCP, with no service account key file anywhere in the
# cluster (see ../k8s/overlays/gcp's KSAs and workload_identity.tf's GSA
# bindings for the other half of this).
resource "google_container_cluster" "this" {
  project  = var.project_id
  name     = var.cluster_name
  location = var.region # regional cluster — control plane survives a single zone outage

  enable_autopilot = true

  network    = google_compute_network.this.id
  subnetwork = google_compute_subnetwork.gke.id

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false # control plane still reachable from outside the VPC (e.g. this Terraform run, kubectl from a laptop with the right IAM) — nodes themselves have no public IP either way
    master_ipv4_cidr_block  = "172.16.0.16/28"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  release_channel {
    channel = "REGULAR"
  }

  deletion_protection = true

  depends_on = [google_project_service.apis, google_compute_router_nat.this]
}
