from app.db.base import Base
from app.models import SiteSettings


async def test_defaults_carry_the_exact_contact_details(sqlite_session_factory):
    engine = sqlite_session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with sqlite_session_factory() as session:
        session.add(SiteSettings())
        await session.commit()
        row = await session.get(SiteSettings, 1)

    # SRS 2.5: contact details must match the brand record exactly.
    assert row.phone_numbers == ["+2348060036531", "+2349024662143"]
    assert row.whatsapp_link == "https://wa.me/2348060036531"
    assert row.email == "goodnessngwuta@gmail.com"
    assert row.address is None
