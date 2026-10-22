import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.seed import seed
from app.main import app

client = TestClient(app)


@pytest.fixture
async def tables(sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def test_404_before_seed(use_database, tables):
    assert client.get("/settings").status_code == 404


async def test_returns_exact_contact_details_after_seed(use_database, tables, sqlite_session_factory):
    async with sqlite_session_factory() as session:
        await seed(session)

    body = client.get("/settings").json()

    assert body["phone_numbers"] == ["+2348060036531", "+2349024662143"]
    assert body["whatsapp_link"] == "https://wa.me/2348060036531"
    assert body["email"] == "goodnessngwuta@gmail.com"
    assert "id" not in body  # internal fields are not exposed
