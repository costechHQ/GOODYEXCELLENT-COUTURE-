from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import get_session
from app.main import app

client = TestClient(app)


def test_health_db_ok_when_database_answers(use_database):
    assert client.get("/health/db").json() == {"status": "ok"}


def test_health_db_503_when_database_is_down():
    class Broken:
        async def execute(self, *args, **kwargs):
            raise ConnectionRefusedError

    async def override():
        yield Broken()

    app.dependency_overrides[get_session] = override
    try:
        response = client.get("/health/db")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503


async def test_session_runs_a_query(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        assert await session.scalar(text("SELECT 41 + 1")) == 42
