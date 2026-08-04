from fastapi import Request

from .embedder import Embedder


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder
