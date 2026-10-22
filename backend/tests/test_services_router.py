import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.seed import seed
from app.main import app
from app.models import Service

client = TestClient(app)


@pytest.fixture
async def seeded(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as session:
        await seed(session)
        session.add(Service(title="Hidden", slug="hidden", description="x", visible=False))
        await session.commit()


def test_list_returns_visible_services_in_display_order(seeded):
    body = client.get("/services").json()
    assert len(body) == 8  # the hidden one is excluded
    assert [s["slug"] for s in body][:3] == ["senator-wear", "kaftans", "suits-and-formal-wear"]
    assert set(body[0]) == {"id", "title", "slug", "description", "image_url"}


def test_detail_by_slug(seeded):
    response = client.get("/services/agbada-and-chieftaincy-wears")
    assert response.status_code == 200
    assert response.json()["title"] == "Agbada and Chieftaincy Wears"


@pytest.mark.parametrize("slug", ["hidden", "does-not-exist"])
def test_hidden_or_unknown_slug_is_404(seeded, slug):
    assert client.get(f"/services/{slug}").status_code == 404
