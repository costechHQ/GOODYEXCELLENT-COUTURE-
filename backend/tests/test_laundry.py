import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import Base
from app.main import app
from app.models import Enquiry
from app.models.enums import EnquiryStatus, EnquiryType

client = TestClient(app)

VALID = {"name": "Emeka Nwosu", "phone": "+234 803 111 2222", "garment_type": "Senator, kaftan"}


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


async def test_valid_submission_is_saved(session):
    r = client.post("/enquiries/laundry", json=VALID | {"message": " Pick-up possible? "})

    assert r.status_code == 201
    assert set(r.json()) == {"id", "message"}
    e = (await session.scalars(select(Enquiry))).one()
    assert e.type == EnquiryType.laundry
    assert e.status == EnquiryStatus.new
    assert (e.phone, e.garment_type, e.message) == ("+2348031112222", "Senator, kaftan", "Pick-up possible?")


async def test_message_is_optional(session):
    assert client.post("/enquiries/laundry", json=VALID).status_code == 201


@pytest.mark.parametrize("field", ["name", "phone", "garment_type"])
def test_required_fields(session, field):
    payload = {k: v for k, v in VALID.items() if k != field}
    assert client.post("/enquiries/laundry", json=payload).status_code == 422


@pytest.mark.parametrize(
    "change", [{"phone": "12345"}, {"garment_type": " "}, {"garment_type": "x" * 201}, {"name": "A"}]
)
def test_invalid_values_are_rejected(session, change):
    assert client.post("/enquiries/laundry", json=VALID | change).status_code == 422


@pytest.mark.parametrize("extra", [{"status": "closed"}, {"internal_notes": "x"}, {"type": "order"}])
def test_clients_cannot_set_staff_fields(session, extra):
    assert client.post("/enquiries/laundry", json=VALID | extra).status_code == 422


async def test_nothing_is_saved_when_invalid(session):
    client.post("/enquiries/laundry", json=VALID | {"phone": "bad"})
    assert (await session.scalars(select(Enquiry))).all() == []
