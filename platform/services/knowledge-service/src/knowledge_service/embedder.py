from abc import ABC, abstractmethod


class Embedder(ABC):
    """The contract the embedding provider implements. Only Voyage AI is
    used for now — anything wanting a different embedding model swaps the
    implementation registered in main.py, not this interface."""

    @abstractmethod
    async def embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        """input_type is "document" when indexing, "query" when
        searching — Voyage's models are tuned to expect that distinction."""
