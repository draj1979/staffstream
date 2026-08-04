"""Maps a request path's first segment to the backend service that owns
it. One dict, one place to look when a new service needs to be reachable
through the gateway — nothing else in this service needs to change.
"""

from .config import settings

ROUTES: dict[str, str] = {
    "tenants": settings.tenant_service_url,
    "employees": settings.employee_service_url,
    "auth": settings.auth_service_url,
    "agents": settings.agent_registry_url,
    "generate": settings.llm_gateway_url,
    "chat": settings.openclaw_runtime_url,
    "memory": settings.memory_service_url,
    "documents": settings.knowledge_service_url,
    "search": settings.knowledge_service_url,
    "skills": settings.skill_marketplace_url,
    "connections": settings.skill_marketplace_url,
    "tools": settings.skill_marketplace_url,
}

# The knowledge service's upload endpoint is the one route that needs a
# much larger body-size ceiling than everything else.
UPLOAD_SEGMENTS = {"documents"}


def path_segment(path: str) -> str:
    return path.strip("/").split("/", 1)[0]


def resolve_upstream(path: str) -> str | None:
    return ROUTES.get(path_segment(path))


def max_body_bytes_for_path(path: str) -> int:
    if path_segment(path) in UPLOAD_SEGMENTS:
        return settings.max_upload_body_bytes
    return settings.max_body_bytes
