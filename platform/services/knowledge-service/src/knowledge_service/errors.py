class EmbeddingError(RuntimeError):
    """Raised when the embedding provider call itself fails."""


class UnsupportedContentTypeError(ValueError):
    """Raised when an uploaded file isn't PDF or DOCX."""


class EmptyDocumentError(ValueError):
    """Raised when a file has no extractable text."""
