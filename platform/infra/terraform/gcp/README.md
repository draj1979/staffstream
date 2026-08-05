# GCP deployment — Terraform

Provisions everything StaffStream needs to run on GCP: a private VPC,
Cloud SQL for PostgreSQL (two instances, mirroring the existing
main/pgvector split), Memorystore for Redis, a GKE Autopilot cluster with
Workload Identity, an Artifact Registry repo, Secret Manager entries for
every credential the platform's twelve services need, and the Workload
Identity Federation setup GitHub Actions uses to deploy without a service
account key file. Optionally installs Argo CD and bootstraps it to track
[`../k8s/overlays/gcp`](../k8s/overlays/gcp).

**Not provisioned here, deliberately out of scope:** RabbitMQ stays
in-cluster (`infra/k8s/rabbitmq.yaml`, unchanged) — this task was scoped to
VPC/Cloud SQL/Memorystore/GKE/Artifact Registry/Secret Manager, not a
managed message queue. A production deployment would likely want Pub/Sub
or a managed RabbitMQ instead; that's a reasonable follow-up, not bundled
in here.

**Not validated against a live GCP project or a real `terraform apply`** —
this environment has no `terraform` binary and no GCP credentials. Every
`.tf` file was checked for HCL syntax validity (`python-hcl2` parses all
15 files cleanly) and manually cross-referenced (variable names, resource
references, `for_each` key alignment across files) but has **not** been
through `terraform validate` or `terraform plan` against a real backend.
Run both before trusting this against a real project — see below.

## Apply order

```bash
cd infra/terraform/gcp
cp terraform.tfvars.example terraform.tfvars   # fill in project_id, github_repository, etc.

terraform init   # -backend-config=... if using the commented-out GCS backend in versions.tf

terraform validate
terraform plan

# First-ever apply into a brand-new project: the kubernetes/helm providers
# are configured directly off google_container_cluster.this's own
# attributes (see providers.tf's comment) — Terraform generally handles
# this fine in one pass, but if you hit an error about the cluster not
# existing yet when it tries to configure those providers, apply the
# cluster alone first:
terraform apply -target=google_container_cluster.this

# Then the full apply:
terraform apply
```

After that:

1. **Enable pgvector** — `PROJECT_ID=... ./scripts/enable-pgvector.sh` (needs
   `gcloud`, the Cloud SQL Auth Proxy binary, and `psql` — see that
   script's header comment for why this isn't a Terraform resource).
2. **Populate the manual secrets** — `terraform output manual_secrets_to_populate`
   lists every Secret Manager secret Terraform left at a placeholder value
   (API keys, OAuth client credentials, `JWT_SECRET_KEY`, the two Fernet
   encryption keys). For each:
   ```bash
   echo -n "the real value" | gcloud secrets versions add SECRET_NAME \
     --project=$PROJECT_ID --data-file=-
   ```
   The `*_DATABASE_URL` and `REDIS_URL` secrets are already populated —
   Terraform generated those passwords itself (see `secrets.tf`).
3. **Point kubectl at the cluster** — `terraform output gke_get_credentials_command`.
4. **Install Argo CD** (if you didn't set `install_argocd = true` up
   front) — flip that variable and re-apply, or install it yourself and
   point it at `infra/k8s/overlays/gcp` (see that directory's README for
   what it expects to find already in place: the GSAs and Cloud SQL
   instances this Terraform config creates).
5. Any pod whose SecretProviderClass references a still-placeholder
   secret will fail to mount and won't start — that's expected until step
   2 is done for the secrets that particular service needs (see
   `locals.tf`'s `service_secrets` map for which).
6. **Render the k8s overlay and configure GitHub Actions** — run
   `../../k8s/overlays/gcp/set-gcp-project.sh <project_id> <region> <environment>`
   and commit the result (see that script's own comment for why this is a
   one-time render rather than a build-time step), then set these as
   **repository variables** (not secrets — none of them are sensitive,
   see `../../../.github/workflows/deploy-gcp.yml`'s own comment) in
   GitHub under Settings → Secrets and variables → Actions → Variables:

   | Variable | Value |
   |---|---|
   | `GCP_PROJECT_ID` | `terraform output -raw project_id` (or just your `project_id` tfvar) |
   | `GCP_REGION` | your `region` tfvar |
   | `GCP_WORKLOAD_IDENTITY_PROVIDER` | `terraform output github_actions_workload_identity_provider` |
   | `GCP_DEPLOYER_SA_EMAIL` | `terraform output github_actions_service_account_email` |

   From here, a push to `main` (matching `var.github_deploy_ref`) builds
   and pushes all twelve images and bumps the overlay's image tags; Argo
   CD's automated sync applies that to the cluster. See the workflow
   file's own comments for the full flow.

## Why one root module, not a `modules/` tree

Every resource here is single-instance, single-environment (one VPC, one
GKE cluster, two Cloud SQL instances, one Redis instance) — splitting
`network.tf`/`cloudsql.tf`/`gke.tf`/etc. into separate reusable modules
would be premature abstraction for something this repo only ever deploys
once. The files are organized by concern instead (one file per GCP
service/concept), which reads just as clearly for a project this size and
is a lot less to navigate. If a second environment (staging, a second
region) is ever needed, extracting modules from these already
concern-separated files is a mechanical refactor, not a redesign.

## Why per-service GSAs and per-secret IAM grants, not one shared identity

The existing local/docker-compose deployment gives every service the
*entire* `staffstream-secrets` Kubernetes Secret via `envFrom`, regardless
of whether it needs most of what's in there (see
`infra/k8s/secret.example.yaml`) — fine for a single-namespace walking
skeleton, not something worth reproducing here. Each of the twelve
services gets its own GSA (`workload_identity.tf`), bound via Workload
Identity to that service's own KSA, with `roles/secretmanager.secretAccessor`
granted only on the specific secrets `locals.tf`'s `service_secrets` map
says it needs. A compromised `skill-marketplace` pod can read Salesforce's
OAuth client secret; it cannot read `ANTHROPIC_API_KEY` or
`tenant-service`'s database password — IAM enforces that boundary, not
just which `SecretProviderClass` happens to be mounted.

## Cost note

Nothing here is sized for "as cheap as possible" — `cloud_sql_tier`
defaults to a real 2 vCPU/7.5GB instance ×2 (main + vector),
`cloud_sql_availability_type`/`redis_tier` default to HA (regional
standby / cross-zone replica). For a dev or demo environment, override
`cloud_sql_availability_type = "ZONAL"` and `redis_tier = "BASIC"` in
`terraform.tfvars` to roughly halve the Cloud SQL/Redis cost — GKE
Autopilot itself only bills for what's actually scheduled (no idle node
cost), so the HPA tuning in `docs/phase10-load-test.md` carries over
directly to what you pay here.
