import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.rate_limit import enquiry_limiter
from app.db.session import get_session
from app.main import app


@pytest.fixture
def sqlite_session_factory():
    """In-memory SQLite stands in for PostgreSQL in fast tests."""
    engine = create_async_engine("sqlite+aiosqlite://")
    yield async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def use_database(sqlite_session_factory):
    async def override():
        async with sqlite_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def fresh_rate_limiter():
    """Every test starts with an empty limiter, so tests never count against each other."""
    enquiry_limiter.reset()
    yield
    enquiry_limiter.reset()
