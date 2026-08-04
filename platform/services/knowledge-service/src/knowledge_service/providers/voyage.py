import voyageai

from ..embedder import Embedder
from ..errors import EmbeddingError

MODEL = "voyage-3-lite"


class VoyageEmbedder(Embedder):
    def __init__(self, api_key: str, model: str = MODEL):
        self._client = voyageai.AsyncClient(api_key=api_key)
        self._model = model

    async def embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        try:
            result = await self._client.embed(texts, model=self._model, input_type=input_type)
        except Exception as exc:  # voyageai raises various HTTP/auth error subclasses
            raise EmbeddingError(f"Voyage AI error: {exc}") from exc
        return result.embeddings
