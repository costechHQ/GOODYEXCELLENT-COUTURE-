import pytest
from sqlalchemy import func, select

from app.db.base import Base
from app.db.seed import seed
from app.models import Service, SiteSettings


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


async def test_seed_creates_the_eight_services_in_order(session):
    await seed(session)
    rows = (await session.scalars(select(Service).order_by(Service.display_order))).all()
    assert [r.slug for r in rows] == [
        "senator-wear",
        "kaftans",
        "suits-and-formal-wear",
        "shirts",
        "trousers",
        "agbada-and-chieftaincy-wears",
        "womens-senator-wear",
        "fashion-consultations",
    ]
    assert all(r.visible for r in rows)


async def test_seed_does_not_overwrite_an_edited_service(session):
    await seed(session)
    senator = await session.scalar(select(Service).where(Service.slug == "senator-wear"))
    senator.description = "Edited by admin"
    await session.commit()

    await seed(session)

    assert await session.scalar(select(func.count()).select_from(Service)) == 8
    senator = await session.scalar(select(Service).where(Service.slug == "senator-wear"))
    assert senator.description == "Edited by admin"
