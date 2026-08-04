class UnknownProviderError(ValueError):
    """Raised when the requested provider isn't registered with the gateway."""


class ProviderError(RuntimeError):
    """Raised when the upstream provider call itself fails (network, auth, rate limit, ...)."""
