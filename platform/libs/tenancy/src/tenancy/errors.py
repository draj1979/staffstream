class TenantContextError(RuntimeError):
    """Raised when a tenant-scoped query runs without a tenant set in context."""


class TenantMismatchError(RuntimeError):
    """Raised when a row's tenant_id doesn't match the request's tenant context."""
