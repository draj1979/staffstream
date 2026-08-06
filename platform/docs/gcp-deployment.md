# Deploying to GCP

How the three pieces of the GCP deployment path fit together:
[`infra/terraform/gcp`](../infra/terraform/gcp) (infrastructure),
[`infra/k8s/overlays/gcp`](../infra/k8s/overlays/gcp) (what runs on it),
and [`.github/workflows/deploy-gcp.yml`](../.github/workflows/deploy-gcp.yml)
(how a code change gets there). Each has its own README with the
file-by-file detail; this doc is the map between them.

```
                                                                    ┌─────────────┐
  git push to main                                                 │   Secret    │
        │                                                          │  Manager    │
        ▼                                                          └──────┬──────┘
┌───────────────────┐        ┌────────────────────┐                       │ per-service,
│  GitHub Actions    │        │  Artifact Registry  │                      │ least-privilege
│  deploy-gcp.yml    │──────▶│  (12 images, :sha)   │                      │ (Workload Identity)
│                     │       └────────────────────┘                       │
│  1. build+push      │                                                    ▼
│  2. kustomize edit  │───┐                                        ┌──────────────┐
│     set image (x12) │    │  commits the tag bump                 │  GKE Autopilot│
└──────────┬──────────┘    │  back to this repo                    │   cluster     │
           │ WIF, no key    ▼                                       │              │
           │ file, scoped  ┌────────────────────────┐               │  ┌────────┐  │
           └──────────────▶│  infra/k8s/overlays/gcp │──────────────▶│  │ Argo CD │  │
     (Artifact Registry    │  (this repo, same commit)│  watches path │  │ syncs   │──┼──▶ 12 Deployments,
      push only — no       └────────────────────────┘                │  └────────┘  │    each with its own
      cluster access)                                                 └──────────────┘    Cloud SQL Auth Proxy
                                                                                             sidecar (DB-backed
                                                                                             services) reaching
                                                                                             Cloud SQL / Memorystore
                                                                                             over private IP
```

## The three pieces

1. **[`infra/terraform/gcp`](../infra/terraform/gcp)** — everything that
   has to exist before any application code runs: the VPC, Cloud SQL
   (two instances), Memorystore, the GKE Autopilot cluster, Artifact
   Registry, every Secret Manager secret, a GSA per service (Workload
   Identity), and the GitHub OIDC trust relationship. Applied once (and
   again on infra changes), not on every code push.

2. **[`infra/k8s/overlays/gcp`](../infra/k8s/overlays/gcp)** — what
   actually runs, as a Kustomize overlay on
   [`infra/k8s/base`](../infra/k8s/base) (the same manifests the
   local/kind deployment uses). Adds the Secret Manager CSI driver
   plumbing and Cloud SQL Auth Proxy sidecars; Argo CD builds this
   directory directly. The one field that changes on every deploy — each
   service's image tag — lives in this directory's `kustomization.yaml`.

3. **[`.github/workflows/deploy-gcp.yml`](../.github/workflows/deploy-gcp.yml)** —
   runs on every push to `main`. Authenticates to GCP via Workload
   Identity Federation (no key file — see
   [`infra/terraform/gcp/github_oidc.tf`](../infra/terraform/gcp/github_oidc.tf)),
   builds and pushes all twelve images, then edits and commits the
   overlay's image tags. That commit — not the workflow itself — is what
   triggers a deploy: Argo CD notices the new commit on the path it
   watches and syncs it. The workflow never authenticates to the cluster
   directly.

## Why the CI → cluster path goes through git, not `kubectl apply`

A more direct pipeline (CI authenticates to GKE, runs `kubectl apply` or
`helm upgrade` itself) is one fewer hop, but it means the CI identity
needs write access to the live cluster — anyone who can trigger that
workflow (or compromise it) can mutate cluster state directly, bypassing
whatever review a PR would have gotten and leaving no diff/rollback trail
beyond CI logs. Routing through a git commit that Argo CD applies means:

- The GitHub Actions deployer GSA ([`github_oidc.tf`](../infra/terraform/gcp/github_oidc.tf))
  only ever needs `roles/artifactregistry.writer` — it has zero GCP
  permissions on Secret Manager, Cloud SQL, or the GKE cluster itself.
- Every deploy is a real git commit — `git log` on
  `infra/k8s/overlays/gcp/kustomization.yaml` is the deploy history, and
  reverting a bad deploy is `git revert` (Argo CD's `selfHeal` then
  reconciles the cluster back to match).
- Argo CD's own diff/sync-status view is the source of truth for "is the
  cluster what git says it should be", not a CI log from three deploys ago.

## What's still a manual (or CI-adjacent) step

- **Populating real secret values** — Terraform creates every Secret
  Manager secret (placeholder values for anything it can't derive
  itself) but doesn't know your Anthropic API key, your Slack app's
  client secret, etc. See
  [`infra/terraform/gcp/README.md`](../infra/terraform/gcp/README.md#apply-order).
- **Enabling pgvector** — one SQL statement, not something Terraform's
  GCP provider models as a resource. See
  [`infra/terraform/gcp/scripts/enable-pgvector.sh`](../infra/terraform/gcp/scripts/enable-pgvector.sh).
- **The Secret Manager CSI driver's cluster-level install** — a one-time
  `gcloud container clusters update --enable-secret-manager` (or the
  Helm chart), not a namespace-scoped resource this repo's Kustomize
  overlay manages. See
  [`infra/k8s/overlays/gcp/README.md`](../infra/k8s/overlays/gcp/README.md#prerequisites).
- **Rotating a secret** — `gcloud secrets versions add`, then restart the
  owning pod(s) (the CSI driver reads "latest" at mount time, not
  continuously) — there's no automatic rotation/reload wired up.

## What this explicitly does not cover

Scoped to what was asked: VPC, Cloud SQL (pgvector-enabled, private IP),
Memorystore, GKE Autopilot with Workload Identity, Artifact Registry,
Secret Manager, and a WIF-authenticated GitHub Actions → Artifact
Registry → Argo CD deploy path. **RabbitMQ stays in-cluster** (see
[`infra/k8s/base/rabbitmq.yaml`](../infra/k8s/base/rabbitmq.yaml),
untouched by the overlay) — not migrated to a managed queue. A load
balancer / ingress / TLS / DNS setup for the API Gateway's public entry
point, a domain for the Argo CD UI, and multi-region/DR are all real
next steps for an actual production rollout, not included here.

For a simpler, cheaper alternative to this whole path — two VMs and
`docker compose` instead of GKE/Cloud SQL/Memorystore, good for a demo or
proof of concept rather than production — see
[`infra/gcp-vm-demo`](../infra/gcp-vm-demo).

## Verification status

Built and honestly labeled, not claimed as battle-tested:

- Every `.tf` file parses as valid HCL (`python-hcl2`) and was manually
  cross-checked for resource/variable reference consistency — **not**
  run through `terraform validate`/`plan`/`apply` against a real GCP
  project (no `terraform` binary or GCP credentials in the environment
  this was built in).
- Every k8s YAML file, `infra/k8s/base` and `infra/k8s/overlays/gcp`
  both, was actually built with a real `kustomize` binary
  (`kustomize build infra/k8s/base` / `infra/k8s/overlays/gcp`) and the
  merged output inspected line-by-line for a DB-backed and a
  non-DB-backed service — **not** applied to a live cluster
  (`kubectl apply --dry-run=server` needs a reachable API server, which
  this environment didn't have).
- The GitHub Actions workflow's YAML is well-formed and its
  `kustomize edit set image` commands were run for real (against a
  scratch copy of the overlay) and produced the expected diff — the
  workflow itself has not run in GitHub Actions.

Run `terraform plan` and a real `kustomize build` review before trusting
any of this against production, and expect to iterate once it meets a
real GCP project and cluster.
