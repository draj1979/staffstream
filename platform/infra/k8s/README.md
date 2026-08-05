# Kubernetes manifests — single namespace (`staffstream`)

Everything here targets one namespace, matching Phase 6's scope. Not
tested against a live cluster in this environment (none was available) —
validated by parsing every manifest and cross-checking every ConfigMap/
Secret key against each service's actual `Settings` fields. Apply order
matters (namespace and config first, since everything else references
them):

```bash
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml

cp secret.example.yaml secret.yaml   # gitignored — fill in real values
# or generate it imperatively instead, e.g. from your CI secrets store:
#   kubectl create secret generic staffstream-secrets -n staffstream \
#     --from-literal=JWT_SECRET_KEY=... --from-literal=ANTHROPIC_API_KEY=... [...]
kubectl apply -f secret.yaml

kubectl apply -f postgres.yaml
kubectl apply -f postgres-vector.yaml
kubectl apply -f redis.yaml
kubectl apply -f rabbitmq.yaml

kubectl apply -f services/
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
real registry, and pins a real tag instead of `latest`.

## Layout

- `namespace.yaml` — the `staffstream` namespace everything else lives in.
- `configmap.yaml` — non-secret config: inter-service URLs (k8s DNS names,
  e.g. `http://tenant-service:8001`), `REDIS_URL`, and `RABBITMQ_URL`.
- `secret.example.yaml` — template for `JWT_SECRET_KEY`, `ANTHROPIC_API_KEY`,
  `VOYAGE_API_KEY`, the five Phase 10 LLM provider keys, `OAUTH_ENCRYPTION_KEY`
  + all twelve connectors' OAuth app credentials, `SSO_ENCRYPTION_KEY`,
  Postgres credentials, and every `*_DATABASE_URL` (these live in the
  Secret, not the ConfigMap, because they embed the DB password or another
  secret value). Real deployments should source these from Vault / a cloud
  secret manager instead, per CLAUDE.md's security baseline.
- `postgres.yaml` — backs every service except knowledge-service: a
  ConfigMap holding the same `init-db.sh` used by docker-compose (creates
  the eight non-vector per-service databases), a PVC, Deployment, Service.
  `max_connections` is bumped (Phase 10) to match the per-pod connection
  pool budget (`libs/tenancy`'s `make_engine`) multiplied out across each
  service's `HorizontalPodAutoscaler` — see `services/*.yaml` below and
  [../../docs/phase10-load-test.md](../../docs/phase10-load-test.md).
- `postgres-vector.yaml` — separate `pgvector/pgvector:pg16` instance
  dedicated to knowledge-service, mirroring docker-compose's split (kept
  separate so the pgvector requirement never touches the other services'
  database or its image/collation). `max_connections` bumped the same way,
  just against knowledge-service's own HPA ceiling.
- `redis.yaml` — backs the API Gateway's per-tenant rate limiter.
- `rabbitmq.yaml` — event bus: LLM Gateway and OpenClaw Runtime publish
  usage/interaction/skill events here, Analytics Service consumes them.
- `services/*.yaml` — one Deployment + Service + `HorizontalPodAutoscaler`
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
