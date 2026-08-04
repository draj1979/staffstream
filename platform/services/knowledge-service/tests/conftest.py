import io

import pytest
from httpx import ASGITransport, AsyncClient
from knowledge_service.config import settings
from knowledge_service.db import get_db
from knowledge_service.dependencies import get_embedder
from knowledge_service.main import app
from sqlalchemy.ext.asyncio import AsyncSession

from tenancy import Base, make_engine, make_session_factory

# pgvector's cosine-distance query is real Postgres SQL (`<=>`) — there is
# no meaningful SQLite fallback for it, unlike every other service's
# tests. These tests need a real Postgres+pgvector instance; skip cleanly
# (not a failure) when one isn't reachable, e.g. a contributor running
# `make test` without docker compose up. `docker compose up -d
# postgres-vector` locally, or CI's dedicated job (which sets
# KNOWLEDGE_SERVICE_DATABASE_URL), provide one for real.
TEST_DATABASE_URL = settings.database_url


class FakeEmbedder:
    """Deterministic, free, offline stand-in for Voyage AI. Real pgvector
    cosine-distance math still runs for real against these vectors — only
    the (paid, network) embedding call itself is faked."""

    def __init__(self):
        self.calls: list[tuple[list[str], str]] = []

    async def embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        self.calls.append((texts, input_type))
        return [_fake_vector(text) for text in texts]


def _fake_vector(text: str) -> list[float]:
    """A cheap 512-dim embedding where similar text -> similar vector: each
    dimension accumulates a hash of the words present, so shared vocabulary
    produces similar vectors without needing a real model."""
    vector = [0.0] * 512
    for word in text.lower().split():
        vector[hash(word) % 512] += 1.0
    norm = sum(v * v for v in vector) ** 0.5
    return [v / norm for v in vector] if norm else vector


def make_docx_bytes(paragraphs: list[str]) -> bytes:
    from docx import Document as DocxDocument

    document = DocxDocument()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def make_blank_pdf_bytes() -> bytes:
    """A valid PDF with no extractable text — for testing the
    empty-document rejection path."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture(scope="session")
async def _pg_available():
    engine = make_engine(TEST_DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql("SELECT 1")
    except Exception as exc:
        pytest.skip(f"Postgres+pgvector not reachable at {TEST_DATABASE_URL}: {exc}")
    finally:
        await engine.dispose()
    return True


@pytest.fixture
async def client(_pg_available):
    engine = make_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
            "ON chunks USING hnsw (embedding vector_cosine_ops)"
        )
    session_factory = make_session_factory(engine)

    async def override_get_db() -> AsyncSession:
        async with session_factory() as session:
            yield session

    fake_embedder = FakeEmbedder()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedder] = lambda: fake_embedder
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.fake_embedder = fake_embedder  # type: ignore[attr-defined]
            yield ac
    finally:
        app.dependency_overrides.clear()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
