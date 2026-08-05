# Kubernetes manifests — single namespace (`staffstream`)

Two ways to deploy this, both starting from the same [`base/`](base):

- **Local / kind / minikube** — `base/` as-is: in-cluster Postgres (×2)
  and Redis, a shared `staffstream-secrets` Kubernetes Secret. This is
  what Phase 6 originally shipped.
- **GCP** — [`overlays/gcp/`](overlays/gcp), which replaces the in-cluster
  Postgres/Redis with Cloud SQL/Memorystore and the shared Secret with
  per-service Secret Manager access via the Secrets Store CSI driver. See
  that directory's own README and [`../terraform/gcp`](../terraform/gcp).

Restructured into `base/` + `overlays/` in Phase 10's GCP work — Kustomize
can only have an overlay reference a base living *outside* the overlay's
own directory tree, so a base at this directory's root (with `overlays/`
nested inside it, as it was before) can't be referenced by
`overlays/gcp/kustomization.yaml` without a "cycle detected" error.
Nothing in `base/` changed in content during that move, only its path
(`infra/k8s/namespace.yaml` → `infra/k8s/base/namespace.yaml`, etc.).

Not tested against a live cluster in this environment (none was
available) — validated by parsing every manifest, cross-checking every
ConfigMap/Secret key against each service's actual `Settings` fields, and
(as of the `base`/`overlays` split) actually running
`kustomize build base` and `kustomize build overlays/gcp` locally and
inspecting the merged output for both a DB-backed and non-DB-backed
service.

## Local / kind / minikube

Apply order matters (namespace and config first, since everything else
references them):

```bash
# Either the classic sequence:
kubectl apply -f base/namespace.yaml
kubectl apply -f base/configmap.yaml

cp secret.example.yaml secret.yaml   # gitignored — fill in real values
# or generate it imperatively instead, e.g. from your CI secrets store:
#   kubectl create secret generic staffstream-secrets -n staffstream \
#     --from-literal=JWT_SECRET_KEY=... --from-literal=ANTHROPIC_API_KEY=... [...]
kubectl apply -f secret.yaml

kubectl apply -f base/postgres.yaml
kubectl apply -f base/postgres-vector.yaml
kubectl apply -f base/redis.yaml
kubectl apply -f base/rabbitmq.yaml
kubectl apply -f base/services/

# ...or, once secret.yaml exists, the whole base in one shot:
kubectl apply -k base
```

## Images

Every Deployment references `staffstream/<service>:latest` with
`imagePullPolicy: IfNotPresent` — for local testing (kind/minikube), build
and load each image rather than pushing to a registry:

```bash
docker build -f services/tenant-service/Dockerfile -t staffstream/tenant-service:latest .
kind load docker-image staffstream/tenant-service:latest   # kind only; minikube has its own equivalent
```

A real deployment replaces this with images built and pushed by CI to a
real registry, and pins a real tag instead of `latest` — see
[`../../.github/workflows/deploy-gcp.yml`](../../.github/workflows/deploy-gcp.yml)
for the GCP path's version of this.

## Layout

- `base/namespace.yaml` — the `staffstream` namespace everything else lives in.
- `base/configmap.yaml` — non-secret config: inter-service URLs (k8s DNS
  names, e.g. `http://tenant-service:8001`), `REDIS_URL`, and
  `RABBITMQ_URL`. (The GCP overlay removes `REDIS_URL` from this — see
  `overlays/gcp/README.md`.)
- `secret.example.yaml` — template for `JWT_SECRET_KEY`, `ANTHROPIC_API_KEY`,
  `VOYAGE_API_KEY`, the five Phase 10 LLM provider keys, `OAUTH_ENCRYPTION_KEY`
  + all twelve connectors' OAuth app credentials, `SSO_ENCRYPTION_KEY`,
  Postgres credentials, and every `*_DATABASE_URL` (these live in the
  Secret, not the ConfigMap, because they embed the DB password or another
  secret value). Real deployments should source these from Vault / a cloud
  secret manager instead, per CLAUDE.md's security baseline — the GCP
  overlay does exactly that (Secret Manager, not this file at all).
- `base/postgres.yaml` — backs every service except knowledge-service: a
  ConfigMap holding the same `init-db.sh` used by docker-compose (creates
  the eight non-vector per-service databases), a PVC, Deployment, Service.
  `max_connections` is bumped (Phase 10) to match the per-pod connection
  pool budget (`libs/tenancy`'s `make_engine`) multiplied out across each
  service's `HorizontalPodAutoscaler` — see `base/services/*.yaml` below
  and [../../docs/phase10-load-test.md](../../docs/phase10-load-test.md).
- `base/postgres-vector.yaml` — separate `pgvector/pgvector:pg16` instance
  dedicated to knowledge-service, mirroring docker-compose's split (kept
  separate so the pgvector requirement never touches the other services'
  database or its image/collation). `max_connections` bumped the same way,
  just against knowledge-service's own HPA ceiling.
- `base/redis.yaml` — backs the API Gateway's per-tenant rate limiter.
- `base/rabbitmq.yaml` — event bus: LLM Gateway and OpenClaw Runtime
  publish usage/interaction/skill events here, Analytics Service consumes
  them. Stays in-cluster even on GCP (see `overlays/gcp/README.md`'s
  scope note) — not migrated to a managed queue in this task.
- `base/services/*.yaml` — one Deployment + Service + `HorizontalPodAutoscaler`
  (Phase 10 — none existed before) per backend service. Each Deployment is
  wired with `livenessProbe` on `/healthz` and `readinessProbe` on
  `/readyz` (see each service's own `/readyz` — DB-backed services check
  real DB connectivity; stateless ones just confirm the process is up).
  `api-gateway`'s Service is the one `type: LoadBalancer` — the intended
  external entry point; every other Service is ClusterIP-only. Each HPA is
  CPU-based (`autoscaling/v2`), `minReplicas` matching the Deployment's
  static `replicas:` and `maxReplicas`/CPU target varying by how central
  the service is to the request hot path — see
  [../../docs/phase10-load-test.md](../../docs/phase10-load-test.md) for
  the full table and the load test behind the tuning.
- `overlays/gcp/` — the GCP deployment path; see its own README.
