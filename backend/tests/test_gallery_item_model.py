import pytest
from sqlalchemy.exc import StatementError

from app.db.base import Base
from app.models import GalleryItem
from app.models.enums import GalleryCategory


@pytest.fixture
async def session(sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


def test_categories_match_fr_25():
    assert [c.value for c in GalleryCategory] == [
        "senator", "kaftan", "suit", "shirt", "trouser", "agbada", "womens_senator",
    ]  # fmt: skip


async def test_defaults(session):
    session.add(GalleryItem(image_url="https://cdn.example/a.webp", category=GalleryCategory.suit))
    await session.commit()
    item = await session.get(GalleryItem, 1)
    assert item.featured is False
    assert item.display_order == 0
    assert item.alt_text == ""
    assert item.created_at is not None  # filled in by the database


async def test_rejects_a_category_outside_the_list(session):
    session.add(GalleryItem(image_url="x", category="dress"))
    with pytest.raises(StatementError):
        await session.commit()
