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

client = TestClient(app)

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


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
    """Five enquiries, oldest first. Ids 1 to 5; created_at is set so ordering is predictable."""
    rows = [
        ("consultation", EnquiryStatus.new, "Ada"),
        ("order", EnquiryStatus.contacted, "Bola"),
        ("order", EnquiryStatus.new, "Chika"),
        ("laundry", EnquiryStatus.closed, "Dayo"),
        ("general", EnquiryStatus.new, "Emeka"),
    ]
    for i, (kind, status, name) in enumerate(rows):
        session.add(
            Enquiry(
                type=EnquiryType(kind),
                status=status,
                name=name,
                phone="+2348012345678",
                created_at=T0 + timedelta(hours=i),
            )
        )
    await session.commit()


def names(response):
    return [i["name"] for i in response.json()["items"]]


# --- access control (FR-51) -------------------------------------------------


@pytest.mark.parametrize("path", ["/admin/enquiries", "/admin/enquiries/1"])
async def test_routes_need_a_signed_in_admin(enquiries, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer junk"}).status_code == 401


async def test_no_personal_data_leaks_to_anonymous_visitors(enquiries):
    r = client.get("/admin/enquiries")
    assert "Ada" not in r.text and "+2348012345678" not in r.text


# --- list -------------------------------------------------------------------


async def test_newest_enquiries_come_first(enquiries, auth):
    r = client.get("/admin/enquiries", headers=auth)
    assert names(r) == ["Emeka", "Dayo", "Chika", "Bola", "Ada"]
    assert (r.json()["total"], r.json()["limit"], r.json()["offset"]) == (5, 50, 0)


async def test_the_list_is_a_summary_without_message_or_notes(session, auth):
    session.add(Enquiry(type=EnquiryType.general, name="Fola", message="private text", internal_notes="staff only"))
    await session.commit()

    item = client.get("/admin/enquiries", headers=auth).json()["items"][0]

    assert set(item) == {
        "id", "type", "status", "name", "phone", "email", "preferred_contact", "service", "subject", "created_at",
    }  # fmt: skip
    assert "private text" not in str(item) and "staff only" not in str(item)


async def test_equal_timestamps_fall_back_to_newest_id_first(session, auth):
    for name in ("One", "Two", "Three"):
        session.add(Enquiry(type=EnquiryType.general, name=name, created_at=T0))
    await session.commit()
    assert names(client.get("/admin/enquiries", headers=auth)) == ["Three", "Two", "One"]


async def test_filter_by_type(enquiries, auth):
    r = client.get("/admin/enquiries?type=order", headers=auth)
    assert names(r) == ["Chika", "Bola"] and r.json()["total"] == 2


async def test_filter_by_status(enquiries, auth):
    r = client.get("/admin/enquiries?status=new", headers=auth)
    assert names(r) == ["Emeka", "Chika", "Ada"] and r.json()["total"] == 3


async def test_filters_combine(enquiries, auth):
    r = client.get("/admin/enquiries?type=order&status=new", headers=auth)
    assert names(r) == ["Chika"] and r.json()["total"] == 1


async def test_no_matches_gives_an_empty_page(enquiries, auth):
    r = client.get("/admin/enquiries?type=laundry&status=new", headers=auth)
    assert r.status_code == 200 and r.json()["items"] == [] and r.json()["total"] == 0


async def test_pagination_keeps_the_full_total(enquiries, auth):
    page1 = client.get("/admin/enquiries?limit=2", headers=auth).json()
    page2 = client.get("/admin/enquiries?limit=2&offset=2", headers=auth).json()
    page3 = client.get("/admin/enquiries?limit=2&offset=4", headers=auth).json()

    assert [i["name"] for i in page1["items"]] == ["Emeka", "Dayo"]
    assert [i["name"] for i in page2["items"]] == ["Chika", "Bola"]
    assert [i["name"] for i in page3["items"]] == ["Ada"]
    assert page1["total"] == page2["total"] == page3["total"] == 5


async def test_pagination_applies_after_filtering(enquiries, auth):
    r = client.get("/admin/enquiries?status=new&limit=1&offset=1", headers=auth).json()
    assert [i["name"] for i in r["items"]] == ["Chika"] and r["total"] == 3


@pytest.mark.parametrize("query", ["type=complaint", "status=archived", "limit=0", "limit=101", "limit=x", "offset=-1"])
async def test_bad_parameters_are_rejected(enquiries, auth, query):
    assert client.get(f"/admin/enquiries?{query}", headers=auth).status_code == 422


# --- detail -----------------------------------------------------------------


async def test_detail_returns_the_whole_record_including_notes(session, auth):
    session.add(
        Enquiry(
            type=EnquiryType.order,
            name="Tunde",
            phone="+2348031112222",
            email="tunde@example.com",
            preferred_contact=ContactMethod.call,
            message="Groomsmen set",
            garment_type="Agbada",
            occasion="Wedding",
            needed_by=date(2026, 12, 20),
            quantity=3,
            fabric_preference="Navy brocade",
            internal_notes="Called twice, no answer",
            created_at=T0,
        )
    )
    await session.commit()

    body = client.get("/admin/enquiries/1", headers=auth).json()

    assert body["name"] == "Tunde" and body["type"] == "order" and body["status"] == "new"
    assert (body["garment_type"], body["quantity"], body["needed_by"]) == ("Agbada", 3, "2026-12-20")
    assert body["internal_notes"] == "Called twice, no answer" and body["message"] == "Groomsmen set"
    assert body["preferred_contact"] == "call" and body["preferred_at"] is None


def test_a_missing_enquiry_is_404(session, auth):
    assert client.get("/admin/enquiries/999", headers=auth).status_code == 404


# --- the public side stays closed ------------------------------------------


async def test_there_is_no_public_way_to_read_enquiries(enquiries):
    assert client.get("/enquiries").status_code in (404, 405)
    assert client.get("/enquiries/1").status_code in (404, 405)
