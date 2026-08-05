# Custom-mode VPC (not the default auto-mode one) — explicit subnets only,
# matching CLAUDE.md's "boring, explicit" preference over whatever GCP
# auto-creates.
resource "google_compute_network" "this" {
  project                 = var.project_id
  name                    = "staffstream-${var.environment}"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

# The one subnet GKE Autopilot's nodes and pods/services live in.
# VPC-native (alias IP) with secondary ranges for pods/services, as
# Autopilot requires. No external IPs on nodes (Autopilot nodes never get
# one) — Cloud NAT below is what gives them internet egress (pulling base
# images, calling out to Claude/OpenAI/etc.).
resource "google_compute_subnetwork" "gke" {
  project                  = var.project_id
  name                     = "staffstream-gke-${var.environment}"
  region                   = var.region
  network                  = google_compute_network.this.id
  ip_cidr_range            = "10.10.0.0/20" # ~4k node IPs, plenty for Autopilot
  private_ip_google_access = true           # lets nodes reach Google APIs (Artifact Registry, Secret Manager) without a public IP

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.20.0.0/14" # ~256k pod IPs
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.30.0.0/20" # ~4k Service ClusterIPs
  }
}

# Private Services Access — the VPC peering Cloud SQL and Memorystore both
# need to hand out a private IP inside this VPC instead of a public one.
# One reserved range shared by both, per Google's own guidance (they're
# both "Google-managed services" using the same peering mechanism).
resource "google_compute_global_address" "private_service_range" {
  project       = var.project_id
  name          = "staffstream-psa-${var.environment}"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 20
  network       = google_compute_network.this.id
}

resource "google_service_networking_connection" "private_service_connection" {
  network                 = google_compute_network.this.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_range.name]
}

# Cloud Router + Cloud NAT: Autopilot nodes have no public IP (private
# cluster, see gke.tf), so this is the only way they reach the public
# internet at all — needed for pulling public base images and for every
# service's own outbound calls (Claude/OpenAI/Gemini/Mistral/DeepSeek/Groq,
# Slack/GitHub/Salesforce/etc. connector OAuth endpoints). Traffic to
# Google APIs (Artifact Registry, Secret Manager, Cloud SQL/Memorystore)
# doesn't need this — private_ip_google_access above covers that path.
resource "google_compute_router" "this" {
  project = var.project_id
  name    = "staffstream-router-${var.environment}"
  region  = var.region
  network = google_compute_network.this.id
}

resource "google_compute_router_nat" "this" {
  project                            = var.project_id
  name                                = "staffstream-nat-${var.environment}"
  router                             = google_compute_router.this.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
