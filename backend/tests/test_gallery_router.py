import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.main import app
from app.models import GalleryItem
from app.models.enums import GalleryCategory as C

client = TestClient(app)


@pytest.fixture
async def gallery(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as session:
        session.add_all(
            [
                GalleryItem(image_url="late", category=C.senator, display_order=2),
                GalleryItem(image_url="first", category=C.senator, featured=True, display_order=0),
                GalleryItem(image_url="kaftan", category=C.kaftan, display_order=1),
            ]
        )
        await session.commit()


def urls(path: str) -> list[str]:
    return [i["image_url"] for i in client.get(path).json()]


def test_returns_all_in_display_order(gallery):
    assert urls("/gallery") == ["first", "kaftan", "late"]


def test_filter_by_category(gallery):
    assert urls("/gallery?category=senator") == ["first", "late"]


def test_filter_featured(gallery):
    assert urls("/gallery?featured=true") == ["first"]
    assert urls("/gallery?featured=false") == ["kaftan", "late"]


def test_filters_combine(gallery):
    assert urls("/gallery?category=senator&featured=false") == ["late"]


def test_pagination(gallery):
    assert urls("/gallery?limit=2") == ["first", "kaftan"]
    assert urls("/gallery?limit=2&offset=2") == ["late"]


@pytest.mark.parametrize("query", ["category=dress", "limit=0", "limit=101", "offset=-1"])
def test_bad_parameters_are_422(gallery, query):
    assert client.get(f"/gallery?{query}").status_code == 422


def test_empty_gallery_is_an_empty_list(use_database, sqlite_session_factory):
    import asyncio

    async def create():
        async with sqlite_session_factory.kw["bind"].begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create())
    assert client.get("/gallery").json() == []
