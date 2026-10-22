from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# The engine owns the pool of connections. Creating it does not connect yet.
engine = create_async_engine(settings.database_url, pool_pre_ping=True)

# A session is one unit of work (a few queries, then commit or roll back).
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed when the request ends."""
    async with SessionLocal() as session:
        yield session
