from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import Base
from app.main import app
from app.models import Enquiry
from app.models.enums import ContactMethod, EnquiryStatus, EnquiryType
from app.schemas.enquiry import _today_in_nigeria

client = TestClient(app)

VALID = {"name": "Tunde Bello", "phone": "08031112222", "preferred_contact": "call", "garment_type": "Agbada"}


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


async def test_full_order_is_saved(session):
    needed_by = (_today_in_nigeria() + timedelta(days=30)).isoformat()
    payload = VALID | {
        "occasion": "Wedding",
        "needed_by": needed_by,
        "quantity": 3,
        "fabric_preference": "Navy blue brocade",
        "message": "Groomsmen set",
    }
    r = client.post("/enquiries/order", json=payload)

    assert r.status_code == 201
    assert set(r.json()) == {"id", "message"}
    e = (await session.scalars(select(Enquiry))).one()
    assert e.type == EnquiryType.order
    assert e.status == EnquiryStatus.new
    assert (e.phone, e.preferred_contact) == ("+2348031112222", ContactMethod.call)
    assert (e.garment_type, e.occasion, e.quantity) == ("Agbada", "Wedding", 3)
    assert e.needed_by.isoformat() == needed_by
    assert e.fabric_preference == "Navy blue brocade"


async def test_only_contact_fields_and_garment_are_required(session):
    assert client.post("/enquiries/order", json=VALID).status_code == 201


@pytest.mark.parametrize("field", ["name", "phone", "preferred_contact", "garment_type"])
def test_required_fields(session, field):
    payload = {k: v for k, v in VALID.items() if k != field}
    assert client.post("/enquiries/order", json=payload).status_code == 422


def test_today_is_accepted_but_yesterday_is_not(session):
    today = _today_in_nigeria()
    assert client.post("/enquiries/order", json=VALID | {"needed_by": today.isoformat()}).status_code == 201
    past = (today - timedelta(days=1)).isoformat()
    assert client.post("/enquiries/order", json=VALID | {"needed_by": past}).status_code == 422


@pytest.mark.parametrize(
    "change",
    [
        {"phone": "12345"},
        {"garment_type": " "},
        {"quantity": 0},
        {"quantity": 501},
        {"quantity": "many"},
        {"needed_by": "next week"},
        {"occasion": "x" * 201},
        {"fabric_preference": "x" * 201},
    ],
)
def test_invalid_values_are_rejected(session, change):
    assert client.post("/enquiries/order", json=VALID | change).status_code == 422


def test_email_contact_requires_an_email(session):
    assert client.post("/enquiries/order", json=VALID | {"preferred_contact": "email"}).status_code == 422
    ok = VALID | {"preferred_contact": "email", "email": "tunde@example.com"}
    assert client.post("/enquiries/order", json=ok).status_code == 201


@pytest.mark.parametrize("extra", [{"status": "closed"}, {"internal_notes": "x"}, {"type": "laundry"}])
def test_clients_cannot_set_staff_fields(session, extra):
    assert client.post("/enquiries/order", json=VALID | extra).status_code == 422


async def test_nothing_is_saved_when_invalid(session):
    client.post("/enquiries/order", json=VALID | {"quantity": 0})
    assert (await session.scalars(select(Enquiry))).all() == []
