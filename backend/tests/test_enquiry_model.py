import pytest
from sqlalchemy.exc import StatementError

from app.db.base import Base
from app.models import Enquiry
from app.models.enums import ContactMethod, EnquiryStatus, EnquiryType


@pytest.fixture
async def session(sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


def test_enums_match_the_srs():
    assert [t.value for t in EnquiryType] == ["consultation", "order", "laundry", "general"]
    assert [m.value for m in ContactMethod] == ["whatsapp", "call", "email"]
    assert [s.value for s in EnquiryStatus] == ["new", "contacted", "in_progress", "completed", "closed"]


async def test_defaults(session):
    session.add(Enquiry(type=EnquiryType.general, name="Ada"))
    await session.commit()
    e = await session.get(Enquiry, 1)
    assert e.status == EnquiryStatus.new
    assert e.internal_notes is None
    assert e.created_at is not None  # filled in by the database


async def test_stores_a_full_order_enquiry(session):
    session.add(
        Enquiry(
            type=EnquiryType.order,
            name="Chika",
            phone="+2348012345678",
            preferred_contact=ContactMethod.whatsapp,
            garment_type="Senator",
            quantity=3,
        )
    )
    await session.commit()
    e = await session.get(Enquiry, 1)
    assert (e.phone, e.preferred_contact, e.quantity) == ("+2348012345678", ContactMethod.whatsapp, 3)


async def test_rejects_an_unknown_type(session):
    session.add(Enquiry(type="complaint", name="X"))
    with pytest.raises(StatementError):
        await session.commit()
