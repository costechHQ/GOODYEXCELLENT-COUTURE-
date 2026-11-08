import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import Base
from app.main import app
from app.models import Enquiry
from app.models.enums import EnquiryStatus, EnquiryType

client = TestClient(app)

VALID = {"name": "Chika Eze", "email": "chika@example.com", "subject": "Opening hours", "message": "When do you open?"}


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


async def test_message_with_email_only_is_saved(session):
    r = client.post("/enquiries/contact", json=VALID)

    assert r.status_code == 201
    assert set(r.json()) == {"id", "message"}
    e = (await session.scalars(select(Enquiry))).one()
    assert e.type == EnquiryType.general
    assert e.status == EnquiryStatus.new
    assert (e.email, e.phone, e.preferred_contact) == ("chika@example.com", None, None)
    assert (e.subject, e.message) == ("Opening hours", "When do you open?")


async def test_message_with_phone_only_is_normalised(session):
    payload = {k: v for k, v in VALID.items() if k != "email"} | {"phone": "0803 111 2222"}
    assert client.post("/enquiries/contact", json=payload).status_code == 201
    assert (await session.scalars(select(Enquiry))).one().phone == "+2348031112222"


async def test_blank_optional_fields_count_as_missing(session):
    r = client.post("/enquiries/contact", json=VALID | {"phone": "  "})
    assert r.status_code == 201
    assert (await session.scalars(select(Enquiry))).one().phone is None


def test_phone_or_email_is_required(session):
    payload = {k: v for k, v in VALID.items() if k != "email"}
    assert client.post("/enquiries/contact", json=payload).status_code == 422
    assert client.post("/enquiries/contact", json=payload | {"phone": "", "email": ""}).status_code == 422


@pytest.mark.parametrize("field", ["name", "subject", "message"])
def test_required_fields(session, field):
    payload = {k: v for k, v in VALID.items() if k != field}
    assert client.post("/enquiries/contact", json=payload).status_code == 422


@pytest.mark.parametrize(
    "change",
    [{"phone": "12345"}, {"email": "nope"}, {"subject": " "}, {"message": "x" * 2001}, {"subject": "x" * 201}],
)
def test_invalid_values_are_rejected(session, change):
    assert client.post("/enquiries/contact", json=VALID | change).status_code == 422


@pytest.mark.parametrize("extra", [{"status": "closed"}, {"internal_notes": "x"}, {"type": "order"}])
def test_clients_cannot_set_staff_fields(session, extra):
    assert client.post("/enquiries/contact", json=VALID | extra).status_code == 422


async def test_nothing_is_saved_when_invalid(session):
    client.post("/enquiries/contact", json=VALID | {"phone": "bad"})
    assert (await session.scalars(select(Enquiry))).all() == []
