class InvalidTokenError(Exception):
    """Raised when a bearer token is missing, malformed, expired, or has a
    scope the caller isn't allowed to use for this route."""
