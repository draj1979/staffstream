from collections.abc import AsyncIterator

from pgvector.asyncpg import register_vector
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from tenancy import make_engine, make_session_factory

from .config import settings

engine = make_engine(settings.database_url)
SessionFactory = make_session_factory(engine)


@event.listens_for(engine.sync_engine, "connect")
def _register_vector_codec(dbapi_connection, connection_record) -> None:
    # asyncpg needs the vector type codec registered on every new
    # connection — unlike psycopg, it doesn't discover custom Postgres
    # types automatically.
    dbapi_connection.run_async(register_vector)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
