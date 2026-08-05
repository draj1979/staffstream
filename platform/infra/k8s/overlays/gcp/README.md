# GCP overlay

Kustomize overlay on top of [`../../`](../..) (the local/kind base) for
running StaffStream on the GCP infrastructure [`../../../terraform/gcp`](../../../terraform/gcp)
provisions. Composed via Argo CD (see that Terraform config's `argocd.tf`)
or manually with `kubectl apply -k` / `kustomize build`.

## What this overlay changes vs. the base

- **Drops** `postgres.yaml`, `postgres-vector.yaml`, `redis.yaml` —
  Cloud SQL (two instances) and Memorystore replace all three.
- **Adds** a `ServiceAccount` per service ([`service-accounts.yaml`](service-accounts.yaml)),
  annotated for GKE Workload Identity.
- **Adds** a `SecretProviderClass` per service ([`secret-provider-classes.yaml`](secret-provider-classes.yaml)),
  each listing exactly the Secret Manager secrets that service needs —
  synced into a same-named Kubernetes Secret (`secretObjects`) so every
  Deployment's `envFrom` still just references a Secret by name, same as
  today, just no longer the one flat `staffstream-secrets` blob every
  service used to get regardless of need.
- **Patches** every Deployment ([`deployment-patches.yaml`](deployment-patches.yaml)):
  `serviceAccountName`, the CSI secrets volume/mount, `envFrom.secretRef`
  swapped to that service's own synced secret, and — for the 9 DB-backed
  services — a `cloud-sql-proxy` sidecar container.
- **Removes** `REDIS_URL` from the shared ConfigMap (a JSON6902 patch in
  [`kustomization.yaml`](kustomization.yaml)) — it's a Secret Manager
  secret now, since Memorystore has AUTH enabled, unlike the in-cluster
  Redis that ConfigMap value was written for.
- **Keeps** `rabbitmq.yaml` as-is — out of this task's scope, still
  in-cluster (see the Terraform README's "Not provisioned here" note).

## Prerequisites

1. `terraform apply` in [`../../../terraform/gcp`](../../../terraform/gcp)
   has already run — this overlay's `SecretProviderClass`es and
   `cloud-sql-proxy` sidecars reference Secret Manager secrets and Cloud
   SQL instances that config creates; applying this overlay first has
   nothing to point at.
2. Run `./set-gcp-project.sh <project_id> <region> <environment>` once —
   see that script's header comment for why this is a one-time sed pass
   rather than a render-at-sync-time step. Commit the result; Argo CD
   builds this directory as-is.
3. The [Secret Manager CSI driver](https://secrets-store-csi-driver.sigs.k8s.io/)
   and its [GCP provider](https://github.com/GoogleCloudPlatform/secrets-store-csi-driver-provider-gcp)
   must be installed on the cluster — neither is a namespaced resource
   this overlay manages (they're cluster-wide DaemonSets typically
   installed via Helm or GKE's own Secret Manager CSI driver add-on,
   `gcloud container clusters update --enable-secret-manager`). Not
   included here since it's a one-time cluster-level install, not
   something that belongs in a namespace-scoped application overlay.

## Verifying without a live cluster

This environment had no `kustomize`/`kubectl` binary to actually build
this overlay against. Every YAML file here was checked for syntactic
validity (`yaml.safe_load_all` parses all of them) and manually
cross-checked against [`../../../terraform/gcp/locals.tf`](../../../terraform/gcp/locals.tf)'s
`service_secrets` map (same 12 services, same secret lists, generated
from the same source list to avoid transcription drift — see the
generation notes below) — but has **not** been through a real
`kustomize build` or applied to a live cluster. Run
`kustomize build infra/k8s/overlays/gcp` (after `set-gcp-project.sh`) and
review the output before trusting this against production.

`secret-provider-classes.yaml` and `deployment-patches.yaml` were
generated from a small Python script (not committed — it was a one-off,
not a tool this repo needs going forward) that mirrors
`locals.tf`'s `service_secrets` map by hand. If a service's secret list
ever changes in the Terraform config, this overlay's corresponding
`SecretProviderClass` needs the same edit — there's no automated link
between the two beyond both being derived from the same ground truth
documented in `locals.tf`'s own comment.
