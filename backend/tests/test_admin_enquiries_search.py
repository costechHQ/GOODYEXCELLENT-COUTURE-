from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import app
from app.models import AdminUser, Enquiry
from app.models.enums import AdminRole, EnquiryStatus, EnquiryType

client = TestClient(app)

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)

# (type, status, name, phone, email, subject, message, service)
ROWS = [
    ("consultation", "new", "Adaeze Obi", "+2348031112222", "ada@example.com", None, "Wedding agbada please", "Agbada"),
    ("order", "contacted", "Bola Tinubu", "+2348055550000", None, None, "Need 100% cotton shirts", "Shirts"),
    ("order", "new", "Chika Eze", "+447911123456", "chika@example.org", None, "Senator for graduation", None),
    ("general", "closed", "Dayo Ade", None, "dayo@example.com", "Opening hours", "When do you open?", None),
    ("laundry", "new", "Emeka_N", "+2348099998888", None, None, "Two kaftans, snake_case test", None),
]


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
    admin = AdminUser(email="staff@example.com", password_hash=hash_password("x" * 12), role=AdminRole.staff)
    session.add(admin)
    await session.commit()
    return {"Authorization": f"Bearer {create_access_token(admin.id)}"}


@pytest.fixture
async def enquiries(session):
    for i, (kind, status, name, phone, email, subject, message, service) in enumerate(ROWS):
        session.add(
            Enquiry(
                type=EnquiryType(kind), status=EnquiryStatus(status), name=name, phone=phone, email=email,
                subject=subject, message=message, service=service, created_at=T0 + timedelta(hours=i),
            )
        )  # fmt: skip
    await session.commit()


def search(auth, q, extra=""):
    r = client.get(f"/admin/enquiries?q={q}{extra}", headers=auth)
    assert r.status_code == 200, r.text
    return [i["name"] for i in r.json()["items"]], r.json()["total"]


# --- what is searched -------------------------------------------------------


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("Adaeze", ["Adaeze Obi"]),  # name
        ("example.org", ["Chika Eze"]),  # email
        ("opening", ["Dayo Ade"]),  # subject
        ("graduation", ["Chika Eze"]),  # message
        ("Shirts", ["Bola Tinubu"]),  # service
        ("8055550000", ["Bola Tinubu"]),  # part of a phone number
    ],
)
async def test_each_text_field_is_searched(enquiries, auth, q, expected):
    assert search(auth, q)[0] == expected


async def test_search_ignores_capitalisation(enquiries, auth):
    assert search(auth, "ADAEZE")[0] == search(auth, "adaeze")[0] == ["Adaeze Obi"]


async def test_a_match_in_any_field_counts(enquiries, auth):
    assert search(auth, "example.com")[0] == ["Dayo Ade", "Adaeze Obi"]  # emails; newest first


async def test_surrounding_spaces_are_ignored(enquiries, auth):
    assert search(auth, "%20%20Adaeze%20%20")[0] == ["Adaeze Obi"]


async def test_no_match_gives_an_empty_page(enquiries, auth):
    assert search(auth, "zzzz") == ([], 0)


# --- phone numbers ----------------------------------------------------------


@pytest.mark.parametrize("q", ["08031112222", "0803 111 2222", "%2B2348031112222", "2348031112222"])
async def test_phones_match_whatever_format_staff_type(enquiries, auth, q):
    assert search(auth, q)[0] == ["Adaeze Obi"]


async def test_an_international_number_is_found(enquiries, auth):
    assert search(auth, "%2B44%207911%20123456")[0] == ["Chika Eze"]


# --- wildcards are literal --------------------------------------------------


async def test_a_percent_sign_matches_only_a_literal_percent(enquiries, auth):
    assert search(auth, "%25")[0] == ["Bola Tinubu"]  # "100% cotton"


async def test_an_underscore_matches_only_a_literal_underscore(enquiries, auth):
    names, total = search(auth, "_")
    assert names == ["Emeka_N"] and total == 1  # not "any single character"


async def test_an_underscore_pattern_is_not_a_wildcard(enquiries, auth):
    assert search(auth, "snake_case")[0] == ["Emeka_N"]
    assert search(auth, "snakeXcase")[0] == []


async def test_a_backslash_is_harmless(enquiries, auth):
    assert search(auth, "%5C") == ([], 0)


async def test_sql_text_is_just_text(enquiries, auth):
    assert search(auth, "%27%20OR%201%3D1%20--") == ([], 0)
    assert client.get("/admin/enquiries", headers=auth).json()["total"] == 5  # nothing was harmed


# --- blank, limits and combinations ----------------------------------------


@pytest.mark.parametrize("q", ["", "%20%20"])
async def test_a_blank_search_means_no_search(enquiries, auth, q):
    assert search(auth, q)[1] == 5


async def test_the_search_text_is_capped_at_100_characters(enquiries, auth):
    assert client.get(f"/admin/enquiries?q={'a' * 100}", headers=auth).status_code == 200
    assert client.get(f"/admin/enquiries?q={'a' * 101}", headers=auth).status_code == 422


async def test_search_combines_with_type_and_status(enquiries, auth):
    assert search(auth, "example", "&type=consultation")[0] == ["Adaeze Obi"]
    assert search(auth, "example", "&status=closed")[0] == ["Dayo Ade"]
    assert search(auth, "example", "&type=order&status=new")[0] == ["Chika Eze"]


async def test_total_and_paging_apply_to_the_search_results(enquiries, auth):
    # Three matches, newest first: Dayo, Chika, Adaeze.
    assert search(auth, "example", "&limit=1") == (["Dayo Ade"], 3)
    assert search(auth, "example", "&limit=1&offset=1") == (["Chika Eze"], 3)
    assert search(auth, "example", "&limit=1&offset=2") == (["Adaeze Obi"], 3)


# --- access -----------------------------------------------------------------


async def test_search_needs_a_signed_in_admin(enquiries):
    r = client.get("/admin/enquiries?q=Adaeze")
    assert r.status_code == 401 and "Adaeze" not in r.text
