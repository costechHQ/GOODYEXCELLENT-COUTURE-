import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import Base
from app.main import app
from app.models import Enquiry

client = TestClient(app)


def _post_form(form, payload):
    """The order form is multipart (it can carry pictures); the other three forms are JSON."""
    body = {"data": payload} if form == "order" else {"json": payload}
    return client.post(f"/enquiries/{form}", **body)


PHONE = {"name": "Ada Obi", "phone": "08012345678"}
FORMS = {
    "consultation": PHONE | {"preferred_contact": "call"},
    "order": PHONE | {"preferred_contact": "call", "garment_type": "Suit"},
    "laundry": PHONE | {"garment_type": "Suit"},
    "contact": PHONE | {"subject": "Hello", "message": "Hi there"},
}


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


@pytest.mark.parametrize("form", FORMS)
async def test_filled_honeypot_looks_like_success_but_saves_nothing(session, form):
    real = _post_form(form, FORMS[form])
    assert real.status_code == 201

    trapped = _post_form(form, FORMS[form] | {"website": "http://spam.example"})

    assert trapped.status_code == 201
    assert set(trapped.json()) == set(real.json())  # same shape, so a bot cannot tell
    assert len((await session.scalars(select(Enquiry))).all()) == 1  # only the real one


@pytest.mark.parametrize("form", FORMS)
async def test_empty_honeypot_is_saved_normally(session, form):
    for value in ("", None):
        assert _post_form(form, FORMS[form] | {"website": value}).status_code == 201
    assert len((await session.scalars(select(Enquiry))).all()) == 2


async def test_honeypot_value_is_never_stored(session):
    client.post("/enquiries/contact", json=FORMS["contact"])
    e = (await session.scalars(select(Enquiry))).one()
    assert not hasattr(e, "website")


async def test_invalid_submission_still_fails_when_honeypot_is_set(session):
    r = client.post("/enquiries/laundry", json=FORMS["laundry"] | {"phone": "bad", "website": "x"})
    assert r.status_code == 422
