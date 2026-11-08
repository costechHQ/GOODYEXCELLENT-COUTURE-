import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import app
from app.models import AdminUser, SiteSettings
from app.models.enums import AdminRole

client = TestClient(app)
URL = "/admin/settings"

# SRS 2.5: the brand record's contact details, as seeded.
SEEDED_PHONES = ["+2348060036531", "+2349024662143"]
SEEDED_WHATSAPP = "https://wa.me/2348060036531"
SEEDED_EMAIL = "goodnessngwuta@gmail.com"


@pytest.fixture(autouse=True)
def jwt_on(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SecretStr("s" * 40))


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


@pytest.fixture
async def auth(session):
    """A signed-in Staff admin: FR-55 says Admins, so Staff may edit too."""
    admin = AdminUser(email="staff@example.com", password_hash=hash_password("x" * 12), role=AdminRole.staff)
    session.add(admin)
    await session.commit()
    return {"Authorization": f"Bearer {create_access_token(admin.id)}"}


@pytest.fixture
async def site(session):
    session.add(SiteSettings(id=1))
    await session.commit()


def patch(body, headers):
    return client.patch(URL, json=body, headers=headers)


# --- access control (FR-51) -------------------------------------------------


async def test_a_signed_in_admin_is_required(site):
    assert client.patch(URL, json={"email": "x@example.com"}).status_code == 401
    assert client.patch(URL, json={"email": "x@example.com"}, headers={"Authorization": "Bearer junk"}).status_code == 401


async def test_nothing_changes_without_a_token(site):
    client.patch(URL, json={"email": "hacker@example.com", "phone_numbers": ["+2348012345678"]})
    public = client.get("/settings").json()
    assert public["email"] == SEEDED_EMAIL and public["phone_numbers"] == SEEDED_PHONES


async def test_staff_may_edit(site, auth):
    assert patch({"address": "12 Market Road, Enugu"}, auth).status_code == 200


async def test_settings_that_were_never_seeded_give_404(session, auth):
    assert patch({"email": "a@example.com"}, auth).status_code == 404


# --- the seeded contact details survive edits to anything else -------------


async def test_editing_one_field_leaves_the_seeded_contact_details_exactly_as_they_were(site, auth):
    body = patch({"address": "12 Market Road, Enugu"}, auth).json()
    assert body["address"] == "12 Market Road, Enugu"
    assert (body["phone_numbers"], body["whatsapp_link"], body["email"]) == (SEEDED_PHONES, SEEDED_WHATSAPP, SEEDED_EMAIL)


async def test_an_empty_patch_changes_nothing(site, auth):
    r = patch({}, auth)
    assert r.status_code == 200 and r.json()["phone_numbers"] == SEEDED_PHONES


async def test_the_response_has_the_same_shape_as_the_public_settings(site, auth):
    assert patch({"address": "Enugu"}, auth).json() == client.get("/settings").json()


async def test_edits_appear_on_the_public_site_straight_away(site, auth):
    patch({"email": "hello@goody.example", "address": "Enugu"}, auth)
    public = client.get("/settings").json()
    assert (public["email"], public["address"]) == ("hello@goody.example", "Enugu")


# --- phone numbers (FR-33) --------------------------------------------------


async def test_phone_numbers_are_normalised_and_deduplicated_in_order(site, auth):
    body = patch({"phone_numbers": ["0806 003 6531", "+234 902 466 2143", "+2348060036531"]}, auth).json()
    assert body["phone_numbers"] == SEEDED_PHONES


async def test_an_international_number_is_accepted(site, auth):
    assert patch({"phone_numbers": ["+44 7911 123456"]}, auth).json()["phone_numbers"] == ["+447911123456"]


@pytest.mark.parametrize("bad", [[], ["12345"], ["abc"], ["+2348060036531", "nope"]])
async def test_bad_phone_lists_are_rejected(site, auth, bad):
    assert patch({"phone_numbers": bad}, auth).status_code == 422
    assert client.get("/settings").json()["phone_numbers"] == SEEDED_PHONES


async def test_at_most_five_numbers(site, auth):
    five = [f"+23480600365{n:02d}" for n in range(5)]
    assert patch({"phone_numbers": five}, auth).status_code == 200
    assert patch({"phone_numbers": five + ["+2348060036599"]}, auth).status_code == 422


# --- links ------------------------------------------------------------------


async def test_https_links_are_accepted_and_trimmed(site, auth):
    body = patch({"whatsapp_link": "  https://wa.me/2349024662143 ", "map_link": "https://maps.app.goo.gl/abc123"}, auth).json()
    assert (body["whatsapp_link"], body["map_link"]) == ("https://wa.me/2349024662143", "https://maps.app.goo.gl/abc123")


@pytest.mark.parametrize(
    "bad",
    ["javascript:alert(1)", "data:text/html,x", "http://wa.me/2348060036531", "wa.me/2348060036531", "/relative", "ftp://x.example/a", " ", ""],
)
@pytest.mark.parametrize("field", ["whatsapp_link", "map_link"])
async def test_unsafe_or_insecure_links_are_rejected(site, auth, field, bad):
    assert patch({field: bad}, auth).status_code == 422
    assert client.get("/settings").json()["whatsapp_link"] == SEEDED_WHATSAPP


async def test_link_length_limits(site, auth):
    assert patch({"whatsapp_link": "https://wa.me/" + "1" * 290}, auth).status_code == 422  # over 300
    assert patch({"map_link": "https://maps.example/" + "a" * 490}, auth).status_code == 422  # over 500


# --- email and address ------------------------------------------------------


async def test_email_is_validated(site, auth):
    assert patch({"email": "not-an-email"}, auth).status_code == 422
    assert patch({"email": "hello@goody.example"}, auth).json()["email"] == "hello@goody.example"


@pytest.mark.parametrize("bad", ["", "   ", "x" * 501])
async def test_a_bad_address_is_rejected(site, auth, bad):
    assert patch({"address": bad}, auth).status_code == 422


# --- opening hours ----------------------------------------------------------


async def test_opening_hours_by_day(site, auth):
    hours = {"monday": " 9:00 AM - 6:00 PM ", "saturday": "10:00 AM - 3:00 PM", "sunday": "Closed"}
    body = patch({"opening_hours": hours}, auth).json()
    assert body["opening_hours"] == {"monday": "9:00 AM - 6:00 PM", "saturday": "10:00 AM - 3:00 PM", "sunday": "Closed"}


async def test_opening_hours_replace_the_old_value_they_are_not_merged(site, auth):
    patch({"opening_hours": {"monday": "9 to 5", "tuesday": "9 to 5"}}, auth)
    assert patch({"opening_hours": {"friday": "Closed"}}, auth).json()["opening_hours"] == {"friday": "Closed"}


@pytest.mark.parametrize(
    "bad",
    [{"funday": "9 to 5"}, {"Monday": "9 to 5"}, {"monday": ""}, {"monday": "   "}, {"monday": "x" * 61}, {"monday": 9}, ["monday"], "9 to 5"],
)
async def test_bad_opening_hours_are_rejected(site, auth, bad):
    assert patch({"opening_hours": bad}, auth).status_code == 422


# --- social links -----------------------------------------------------------


async def test_social_links(site, auth):
    links = {"instagram": "https://instagram.com/goodyexcellent", "facebook": "https://facebook.com/goodyexcellent"}
    assert patch({"social_links": links}, auth).json()["social_links"] == links


async def test_social_links_replace_the_old_value(site, auth):
    patch({"social_links": {"instagram": "https://instagram.com/a", "tiktok": "https://tiktok.com/@a"}}, auth)
    assert patch({"social_links": {"facebook": "https://facebook.com/a"}}, auth).json()["social_links"] == {
        "facebook": "https://facebook.com/a"
    }


@pytest.mark.parametrize(
    "bad",
    [
        {"Instagram": "https://instagram.com/a"},  # capital letter
        {"insta gram": "https://instagram.com/a"},
        {"x-twitter": "https://x.com/a"},
        {"a": "https://x.com/a"},  # too short
        {"instagram": "http://instagram.com/a"},  # not https
        {"instagram": "javascript:alert(1)"},
        {"instagram": ""},
        {f"net{i}": "https://x.example/a" for i in range(11)},  # more than ten
    ],
)
async def test_bad_social_links_are_rejected(site, auth, bad):
    assert patch({"social_links": bad}, auth).status_code == 422


# --- clearing and nulls -----------------------------------------------------


async def test_optional_fields_can_be_cleared_with_null(site, auth):
    patch({"address": "Enugu", "map_link": "https://maps.example/x", "opening_hours": {"monday": "9 to 5"},
           "social_links": {"instagram": "https://instagram.com/a"}}, auth)  # fmt: skip
    body = patch({"address": None, "map_link": None, "opening_hours": None, "social_links": None}, auth).json()
    assert (body["address"], body["map_link"], body["opening_hours"], body["social_links"]) == (None, None, None, None)
    assert body["phone_numbers"] == SEEDED_PHONES  # the required ones are untouched


async def test_clearing_stores_a_true_sql_null_not_the_json_text_null(site, session, auth):
    patch({"opening_hours": {"monday": "9 to 5"}, "social_links": {"instagram": "https://instagram.com/a"}}, auth)
    patch({"opening_hours": None, "social_links": None}, auth)

    row = (await session.execute(text("select opening_hours is null, social_links is null from site_settings"))).one()

    assert tuple(row) == (1, 1) or tuple(row) == (True, True)  # SQLite returns 1, PostgreSQL True


@pytest.mark.parametrize("field", ["phone_numbers", "whatsapp_link", "email"])
async def test_the_ways_to_reach_the_brand_cannot_be_cleared(site, auth, field):
    assert patch({field: None}, auth).status_code == 422
    public = client.get("/settings").json()
    assert (public["phone_numbers"], public["whatsapp_link"], public["email"]) == (SEEDED_PHONES, SEEDED_WHATSAPP, SEEDED_EMAIL)


# --- unknown fields ---------------------------------------------------------


@pytest.mark.parametrize("extra", [{"id": 2}, {"phone": "08012345678"}, {"is_admin": True}, {"password_hash": "x"}])
async def test_unknown_fields_are_rejected(site, auth, extra):
    assert patch(extra, auth).status_code == 422


async def test_a_rejected_request_changes_nothing_even_when_part_of_it_was_valid(site, auth):
    r = patch({"address": "A valid new address", "whatsapp_link": "javascript:alert(1)"}, auth)
    assert r.status_code == 422
    assert client.get("/settings").json()["address"] is None
