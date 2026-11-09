import csv
import io
import re
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import app
from app.models import AdminUser, Enquiry
from app.models.enums import AdminRole, ContactMethod, EnquiryStatus, EnquiryType
from app.routers import admin_enquiries

client = TestClient(app)

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
URL = "/admin/enquiries/export.csv"
HEADER = [
    "id", "created_at", "type", "status", "name", "phone", "email", "preferred_contact", "service",
    "subject", "message", "preferred_at", "garment_type", "occasion", "needed_by", "quantity",
    "fabric_preference", "internal_notes",
]  # fmt: skip


@pytest.fixture(autouse=True)
def jwt_on(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SecretStr("s" * 40))


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


async def _headers(session, email, role):
    admin = AdminUser(email=email, password_hash=hash_password("x" * 12), role=role)
    session.add(admin)
    await session.commit()
    return {"Authorization": f"Bearer {create_access_token(admin.id)}"}


@pytest.fixture
async def owner(session):
    return await _headers(session, "owner@example.com", AdminRole.owner)


@pytest.fixture
async def staff(session):
    return await _headers(session, "staff@example.com", AdminRole.staff)


def add(session, name, hours=0, **kw):
    defaults = {"type": EnquiryType.general, "created_at": T0 + timedelta(hours=hours)}
    session.add(Enquiry(name=name, **(defaults | kw)))


def rows(response):
    """Parse the downloaded file back into dicts, exactly as a spreadsheet would read it."""
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))


# --- who may download (the file holds clients' personal details) ------------


async def test_anonymous_visitors_get_nothing(session):
    add(session, "Ada Obi", phone="+2348031112222")
    await session.commit()
    r = client.get(URL)
    assert r.status_code == 401 and "Ada" not in r.text and "+2348031112222" not in r.text


async def test_a_bad_token_gets_nothing(session):
    assert client.get(URL, headers={"Authorization": "Bearer junk"}).status_code == 401


async def test_staff_are_refused_and_see_no_data(session, staff):
    add(session, "Ada Obi", phone="+2348031112222")
    await session.commit()
    r = client.get(URL, headers=staff)
    assert r.status_code == 403 and "Ada" not in r.text and "+2348031112222" not in r.text


async def test_the_owner_can_download(session, owner):
    add(session, "Ada Obi")
    await session.commit()
    assert client.get(URL, headers=owner).status_code == 200


async def test_staff_can_still_use_the_ordinary_routes(session, staff):
    assert client.get("/admin/enquiries", headers=staff).status_code == 200


# --- the file ---------------------------------------------------------------


async def test_it_downloads_as_a_csv_attachment_that_is_never_cached(session, owner):
    add(session, "Ada Obi")
    await session.commit()
    r = client.get(URL, headers=owner)

    assert r.headers["content-type"] == "text/csv; charset=utf-8"
    assert re.fullmatch(r'attachment; filename="enquiries-\d{4}-\d{2}-\d{2}\.csv"', r.headers["content-disposition"])
    assert r.headers["cache-control"] == "no-store"
    assert r.content.startswith(b"\xef\xbb\xbf")  # BOM, so Excel reads accents correctly


async def test_the_header_row_lists_every_column(session, owner):
    r = client.get(URL, headers=owner)
    assert r.content.decode("utf-8-sig").splitlines()[0].split(",") == HEADER


async def test_an_empty_result_is_just_the_header(session, owner):
    r = client.get(URL, headers=owner)
    assert r.status_code == 200 and rows(r) == []


async def test_every_field_is_exported(session, owner):
    add(
        session, "Tunde Bello", type=EnquiryType.order, status=EnquiryStatus.contacted, phone="+2348031112222",
        email="tunde@example.com", preferred_contact=ContactMethod.call, service="Agbada", subject=None,
        message="Groomsmen set", preferred_at=T0, garment_type="Agbada", occasion="Wedding",
        needed_by=date(2026, 12, 20), quantity=3, fabric_preference="Navy brocade",
        internal_notes="Called twice",
    )  # fmt: skip
    await session.commit()

    (row,) = rows(client.get(URL, headers=owner))

    assert row["id"] == "1" and row["type"] == "order" and row["status"] == "contacted"
    assert (row["name"], row["phone"], row["email"]) == ("Tunde Bello", "+2348031112222", "tunde@example.com")
    assert (row["preferred_contact"], row["service"], row["subject"]) == ("call", "Agbada", "")
    assert (row["needed_by"], row["quantity"], row["internal_notes"]) == ("2026-12-20", "3", "Called twice")
    assert row["created_at"].startswith("2026-11-01T09:00:00")


async def test_newest_enquiries_come_first(session, owner):
    for i, name in enumerate(["Ada", "Bola", "Chika"]):
        add(session, name, hours=i)
    await session.commit()
    assert [r["name"] for r in rows(client.get(URL, headers=owner))] == ["Chika", "Bola", "Ada"]


async def test_commas_quotes_and_line_breaks_stay_inside_their_cell(session, owner):
    message = 'Hello, "boss"\nSecond line, with a comma'
    add(session, "Ada", message=message)
    await session.commit()
    (row,) = rows(client.get(URL, headers=owner))
    assert row["message"] == message and row["name"] == "Ada"


async def test_accented_and_non_latin_names_survive(session, owner):
    add(session, "Chidiébere Okonkwò")
    await session.commit()
    assert rows(client.get(URL, headers=owner))[0]["name"] == "Chidiébere Okonkwò"


# --- filters match the list -------------------------------------------------


@pytest.fixture
async def mixed(session):
    add(session, "Ada", 0, type=EnquiryType.consultation, status=EnquiryStatus.new, email="ada@example.com")
    add(session, "Bola", 1, type=EnquiryType.order, status=EnquiryStatus.contacted, message="100% cotton")
    add(session, "Chika", 2, type=EnquiryType.order, status=EnquiryStatus.new, email="chika@example.org")
    add(session, "Dayo", 3, type=EnquiryType.general, status=EnquiryStatus.closed)
    await session.commit()


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", ["Dayo", "Chika", "Bola", "Ada"]),
        ("?type=order", ["Chika", "Bola"]),
        ("?status=new", ["Chika", "Ada"]),
        ("?type=order&status=new", ["Chika"]),
        ("?q=example", ["Chika", "Ada"]),
        ("?q=%25", ["Bola"]),
        ("?q=example&type=consultation", ["Ada"]),
        ("?q=nobody", []),
        ("?q=%20", ["Dayo", "Chika", "Bola", "Ada"]),
    ],
)
async def test_the_same_filters_as_the_list_apply(mixed, owner, query, expected):
    export = [r["name"] for r in rows(client.get(URL + query, headers=owner))]
    listed = [i["name"] for i in client.get(f"/admin/enquiries{query}", headers=owner).json()["items"]]
    assert export == expected == listed


async def test_export_ignores_paging_and_returns_every_match(mixed, owner):
    assert len(rows(client.get(URL + "?limit=1&offset=3", headers=owner))) == 4


@pytest.mark.parametrize("query", ["?type=complaint", "?status=archived", "?q=" + "a" * 101])
async def test_bad_filters_are_rejected(mixed, owner, query):
    assert client.get(URL + query, headers=owner).status_code == 422


async def test_too_many_matches_are_refused_not_cut_short(session, owner, monkeypatch):
    monkeypatch.setattr(admin_enquiries, "MAX_EXPORT_ROWS", 2)
    for i in range(3):
        add(session, f"Person {i}", i)
    await session.commit()

    r = client.get(URL, headers=owner)
    assert r.status_code == 422 and "narrow the filters" in r.json()["detail"]
    assert client.get(URL + "?q=Person 0", headers=owner).status_code == 200  # a narrower search works


# --- spreadsheet formula injection ------------------------------------------


@pytest.mark.parametrize(
    "dangerous",
    ['=HYPERLINK("http://evil.example","click")', "+1+1", "-2+3", "@SUM(A1:A9)", "\t=1+1", "\r=1+1"],
)
async def test_cells_that_would_run_as_formulas_are_neutralised(session, owner, dangerous):
    add(session, dangerous, message=dangerous, internal_notes=dangerous, subject=dangerous)
    await session.commit()

    (row,) = rows(client.get(URL, headers=owner))

    for column in ("name", "message", "internal_notes", "subject"):
        assert row[column] == "'" + dangerous, column  # now plain text in Excel and Sheets


async def test_normal_text_and_real_phone_numbers_are_left_alone(session, owner):
    add(session, "Ada Obi", phone="+2348031112222", message="Wedding - 3 pieces", email="ada@example.com")
    await session.commit()
    (row,) = rows(client.get(URL, headers=owner))
    assert row["phone"] == "+2348031112222"  # a normalised number is safe, so no apostrophe
    assert (row["name"], row["message"], row["email"]) == ("Ada Obi", "Wedding - 3 pieces", "ada@example.com")


async def test_a_plus_sign_that_is_not_a_phone_number_is_still_neutralised(session, owner):
    add(session, "Ada", phone="+234 803 111 2222 =cmd")
    await session.commit()
    assert rows(client.get(URL, headers=owner))[0]["phone"].startswith("'+234")


# --- routing ----------------------------------------------------------------


async def test_the_export_route_does_not_clash_with_enquiry_ids(session, owner):
    add(session, "Ada Obi")
    await session.commit()
    assert client.get(URL, headers=owner).status_code == 200
    assert client.get("/admin/enquiries/1", headers=owner).json()["name"] == "Ada Obi"
    assert client.get("/admin/enquiries/export", headers=owner).status_code == 422  # still just a bad id


async def test_exporting_changes_nothing(session, owner):
    add(session, "Ada Obi")
    await session.commit()
    before = client.get("/admin/enquiries", headers=owner).json()
    client.get(URL, headers=owner)
    assert client.get("/admin/enquiries", headers=owner).json() == before
