from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from tenancy import make_engine, make_session_factory

from .config import settings

engine = make_engine(settings.database_url)
SessionFactory = make_session_factory(engine)

# Deliberately NOT registering pgvector.asyncpg's register_vector codec
# here. pgvector.sqlalchemy.Vector's own bind_processor (see
# site-packages/pgvector/sqlalchemy/vector.py) already stringifies every
# embedding to pgvector's text literal format before it reaches the
# DBAPI, for every driver, asyncpg included — that's enough on its own
# for Postgres to accept it as a query parameter. Registering the raw
# asyncpg codec on top of that made asyncpg intercept the *already
# ORM-stringified* value and hand it to the codec's encoder, which
# expects a raw list/ndarray, not a string — every vector-comparison
# query (search_chunks' cosine_distance, i.e. every /search call and
# every chat turn that touches knowledge) failed with
# `asyncpg.exceptions.DataError: ... (expected list or ndarray)` until
# this was removed.


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
