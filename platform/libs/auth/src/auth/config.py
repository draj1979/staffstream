import os

# Unlike per-service DB URLs, this must be IDENTICAL across every service
# that mints or verifies tokens — so it's a single unprefixed env var
# rather than going through each service's own Settings/env_prefix.
#
# Local-dev default only. Real deployments must set JWT_SECRET_KEY from
# Vault / Secret Manager, never from a committed file (see CLAUDE.md
# security baseline).
JWT_SECRET_KEY = os.environ.get(
    "JWT_SECRET_KEY", "dev-only-insecure-shared-secret-do-not-use-in-production"
)
JWT_ALGORITHM = "HS256"

ACCESS_TOKEN_TTL_SECONDS = int(os.environ.get("ACCESS_TOKEN_TTL_SECONDS", 15 * 60))
SYSTEM_TOKEN_TTL_SECONDS = 60
REFRESH_TOKEN_TTL_DAYS = int(os.environ.get("REFRESH_TOKEN_TTL_DAYS", 30))
