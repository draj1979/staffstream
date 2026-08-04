from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from tenancy import make_engine, make_session_factory

from .config import settings

engine = make_engine(settings.database_url)
SessionFactory = make_session_factory(engine)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
