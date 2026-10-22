import pytest
from sqlalchemy import func, select

from app.db.base import Base
from app.db.seed import seed
from app.models import SiteSettings


@pytest.fixture
async def session(sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


async def test_seed_creates_site_settings_with_exact_contacts(session):
    await seed(session)
    row = await session.get(SiteSettings, 1)
    assert row.phone_numbers == ["+2348060036531", "+2349024662143"]
    assert row.whatsapp_link == "https://wa.me/2348060036531"


async def test_seed_twice_keeps_one_row_and_does_not_overwrite_edits(session):
    await seed(session)
    (await session.get(SiteSettings, 1)).address = "Enugu"
    await session.commit()

    await seed(session)

    assert await session.scalar(select(func.count()).select_from(SiteSettings)) == 1
    assert (await session.get(SiteSettings, 1)).address == "Enugu"
