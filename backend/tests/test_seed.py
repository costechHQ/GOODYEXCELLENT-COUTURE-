from sqlalchemy import func, select

from app.db.seed import SERVICES, seed
from app.models import Service, SiteSettings


async def test_seed_creates_services_and_exact_contacts(session):
    await seed(session)
    assert await session.scalar(select(func.count()).select_from(Service)) == len(SERVICES) == 8
    row = await session.get(SiteSettings, 1)
    assert row.phone_numbers == ["+2348060036531", "+2349024662143"]
    assert row.whatsapp_link == "https://wa.me/2348060036531"
    assert row.email == "goodnessngwuta@gmail.com"


async def test_seed_is_idempotent(session):
    await seed(session)
    await seed(session)
    assert await session.scalar(select(func.count()).select_from(Service)) == 8
