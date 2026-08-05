# Optional (var.install_argocd, off by default — see variables.tf) so a
# first bring-up doesn't try to install into a cluster that isn't
# reachable/ready yet. Installs Argo CD itself, then a single root
# "app of apps" Application pointed at ../k8s/overlays/gcp — from there,
# Argo CD (not this Terraform config, and not the GitHub Actions workflow
# directly) owns applying every Deployment/Service/HPA/SecretProviderClass
# in this repo. CI's job ends at "push a new image tag to git" (see
# ../../.github/workflows/deploy-gcp.yml); Argo CD's own sync/diff/rollback
# is what actually changes the cluster.
#
# Known bring-up ordering caveat (same shape as providers.tf's GKE one):
# kubernetes_manifest for the Application CRD needs Argo CD's own CRDs to
# already exist, which the Helm release below installs — on a genuinely
# first apply, run `terraform apply -target=helm_release.argocd[0]` once
# before the full apply if the Application resource errors on "no matches
# for kind Application".
resource "kubernetes_namespace" "argocd" {
  count = var.install_argocd ? 1 : 0
  metadata {
    name = var.argocd_namespace
  }
  depends_on = [google_container_cluster.this]
}

resource "helm_release" "argocd" {
  count      = var.install_argocd ? 1 : 0
  name       = "argocd"
  namespace  = kubernetes_namespace.argocd[0].metadata[0].name
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = "7.7.11"

  # Defaults are otherwise fine for a single-cluster, single-tenant Argo CD
  # install — no values overrides needed to get a working GitOps
  # controller. Ingress/external access to the Argo CD UI is deliberately
  # left unconfigured here (`kubectl port-forward` for now); exposing it
  # is an environment-specific choice (domain, TLS cert, SSO) outside this
  # config's scope.
}

resource "kubernetes_manifest" "argocd_root_app" {
  count = var.install_argocd ? 1 : 0

  manifest = {
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata = {
      name      = "staffstream-gcp"
      namespace = kubernetes_namespace.argocd[0].metadata[0].name
    }
    spec = {
      project = "default"
      source = {
        repoURL        = var.argocd_git_repo_url
        targetRevision = "HEAD"
        path           = "infra/k8s/overlays/gcp"
      }
      destination = {
        server    = "https://kubernetes.default.svc"
        namespace = var.k8s_namespace
      }
      syncPolicy = {
        automated = {
          prune    = true # a resource removed from the overlay gets removed from the cluster too, not left orphaned
          selfHeal = true # a manual kubectl edit against a live resource gets reverted back to what git says, not silently drift
        }
        syncOptions = ["CreateNamespace=true"]
      }
    }
  }

  depends_on = [helm_release.argocd]
}
