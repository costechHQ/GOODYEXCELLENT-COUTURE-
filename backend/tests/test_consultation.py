import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import Base
from app.main import app
from app.models import Enquiry
from app.models.enums import ContactMethod, EnquiryStatus, EnquiryType

client = TestClient(app)

VALID = {"name": "Ada Obi", "phone": "0801 234 5678", "preferred_contact": "whatsapp"}


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


async def test_valid_submission_is_saved(session):
    r = client.post("/enquiries/consultation", json=VALID | {"service": "Suits", "message": " Hello "})

    assert r.status_code == 201
    assert set(r.json()) == {"id", "message"}
    e = (await session.scalars(select(Enquiry))).one()
    assert e.type == EnquiryType.consultation
    assert e.status == EnquiryStatus.new
    assert e.phone == "+2348012345678"  # normalised
    assert e.preferred_contact == ContactMethod.whatsapp
    assert (e.service, e.message) == ("Suits", "Hello")  # message trimmed


def test_response_does_not_leak_staff_fields(session):
    body = client.post("/enquiries/consultation", json=VALID).json()
    assert "status" not in body and "internal_notes" not in body


@pytest.mark.parametrize("field", ["name", "phone", "preferred_contact"])
def test_required_fields(session, field):
    payload = {k: v for k, v in VALID.items() if k != field}
    assert client.post("/enquiries/consultation", json=payload).status_code == 422


@pytest.mark.parametrize(
    "change",
    [
        {"phone": "12345"},
        {"name": " "},
        {"email": "not-an-email"},
        {"preferred_contact": "carrier-pigeon"},
        {"preferred_at": "tomorrow-ish"},
        {"message": "x" * 2001},
    ],
)
def test_invalid_values_are_rejected(session, change):
    assert client.post("/enquiries/consultation", json=VALID | change).status_code == 422


def test_email_contact_requires_an_email(session):
    assert client.post("/enquiries/consultation", json=VALID | {"preferred_contact": "email"}).status_code == 422
    ok = VALID | {"preferred_contact": "email", "email": "ada@example.com"}
    assert client.post("/enquiries/consultation", json=ok).status_code == 201


@pytest.mark.parametrize("extra", [{"status": "closed"}, {"internal_notes": "x"}, {"type": "order"}])
def test_clients_cannot_set_staff_fields(session, extra):
    assert client.post("/enquiries/consultation", json=VALID | extra).status_code == 422


async def test_nothing_is_saved_when_invalid(session):
    client.post("/enquiries/consultation", json=VALID | {"phone": "bad"})
    assert (await session.scalars(select(Enquiry))).all() == []


def test_field_errors_are_reported_together_against_their_fields(session):
    r = client.post("/enquiries/consultation", json=VALID | {"name": "A", "phone": "123"})
    assert {e["loc"][-1] for e in r.json()["detail"]} == {"name", "phone"}
