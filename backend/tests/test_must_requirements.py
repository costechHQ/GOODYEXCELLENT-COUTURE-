"""Backend checks for specific values the SRS fixes in its Must requirements.

Each test names the requirement it protects. The behaviour around these values is tested in the
feature files; these pin the exact wording, lists and limits so a careless edit cannot drift from the SRS.
"""

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.uploads import MAX_ORDER_IMAGES
from app.db.base import Base
from app.db.seed import seed
from app.main import app
from app.models import Service
from app.models.enums import ContactMethod, EnquiryStatus, GalleryCategory

client = TestClient(app)

PHONE = "0801 234 5678"


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


async def test_fr19_the_eight_services_have_the_srs_titles_and_a_description(session):
    await seed(session)
    rows = (await session.scalars(select(Service).order_by(Service.display_order))).all()
    assert [r.title for r in rows] == [
        "Senator Wear",
        "Kaftans",
        "Suits and Formal Wear",
        "Shirts",
        "Trousers",
        "Agbada and Chieftaincy Wears",
        "Women's Senator Wear",
        "Fashion Consultations",
    ]
    assert all(r.description.strip() for r in rows)


def test_fr25_the_gallery_categories_are_exactly_the_seven_in_the_srs():
    assert {c.value for c in GalleryCategory} == {
        "senator",
        "kaftan",
        "suit",
        "shirt",
        "trouser",
        "agbada",
        "womens_senator",
    }


@pytest.mark.parametrize("category", [c.value for c in GalleryCategory])
def test_fr25_every_category_can_be_filtered(session, category):
    assert client.get("/gallery", params={"category": category}).status_code == 200


def test_fr25_an_unknown_category_is_refused(session):
    assert client.get("/gallery", params={"category": "swimwear"}).status_code == 422


def test_fr30_the_contact_methods_are_whatsapp_call_and_email():
    assert {m.value for m in ContactMethod} == {"whatsapp", "call", "email"}


@pytest.mark.parametrize("method", ["whatsapp", "call"])
def test_fr30_each_contact_method_is_accepted(session, method):
    body = {"name": "Ada Obi", "phone": PHONE, "preferred_contact": method}
    assert client.post("/enquiries/consultation", json=body).status_code == 201


def test_fr30_an_unlisted_contact_method_is_refused(session):
    body = {"name": "Ada Obi", "phone": PHONE, "preferred_contact": "carrier-pigeon"}
    assert client.post("/enquiries/consultation", json=body).status_code == 422


def test_fr31_the_defaults_are_five_pictures_of_up_to_5_mb_each():
    assert MAX_ORDER_IMAGES == 5
    assert Settings(_env_file=None).max_upload_bytes == 5 * 1024 * 1024


def test_fr53_the_enquiry_statuses_are_exactly_the_five_in_the_srs():
    assert [s.value for s in EnquiryStatus] == ["new", "contacted", "in_progress", "completed", "closed"]


FORMS = {
    "consultation": ("json", {"name": "Ada Obi", "phone": PHONE, "preferred_contact": "call"}),
    "order": ("data", {"name": "Ada Obi", "phone": PHONE, "preferred_contact": "call", "garment_type": "Agbada"}),
    "laundry": ("json", {"name": "Ada Obi", "phone": PHONE, "garment_type": "Agbada"}),
    "contact": ("json", {"name": "Ada Obi", "phone": PHONE, "subject": "Hello", "message": "A question"}),
}


@pytest.mark.parametrize("form", FORMS)
def test_fr34_the_confirmation_thanks_the_visitor_and_promises_no_response_time(session, form):
    kind, body = FORMS[form]
    r = client.post(f"/enquiries/{form}", **{kind: body})
    assert r.status_code == 201
    message = r.json()["message"]
    assert "received" in message.lower()
    assert not re.search(r"\d|hour|minute|day|week|immediately|within|soon|asap", message, re.I)
