from datetime import UTC, datetime

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
async def enquiry(session):
    session.add(
        Enquiry(
            type=EnquiryType.order,
            name="Tunde Bello",
            phone="+2348031112222",
            email="tunde@example.com",
            message="Groomsmen set",
            created_at=datetime(2026, 11, 1, tzinfo=UTC),
        )
    )
    await session.commit()


def patch(body, headers, id_=1):
    return client.patch(f"/admin/enquiries/{id_}", json=body, headers=headers)


# --- access control (FR-51) -------------------------------------------------


async def test_a_token_is_required(enquiry):
    assert client.patch("/admin/enquiries/1", json={"status": "closed"}).status_code == 401
    junk = {"Authorization": "Bearer junk"}
    assert client.patch("/admin/enquiries/1", json={"status": "closed"}, headers=junk).status_code == 401


async def test_nothing_changes_without_a_token(session, enquiry):
    client.patch("/admin/enquiries/1", json={"status": "closed", "internal_notes": "hacked"})
    row = await session.get(Enquiry, 1)
    assert (row.status, row.internal_notes) == (EnquiryStatus.new, None)


# --- status (FR-53) ---------------------------------------------------------


async def test_status_starts_as_new_and_can_be_changed(enquiry, auth):
    assert client.get("/admin/enquiries/1", headers=auth).json()["status"] == "new"
    r = patch({"status": "contacted"}, auth)
    assert r.status_code == 200 and r.json()["status"] == "contacted"


@pytest.mark.parametrize("status", ["new", "contacted", "in_progress", "completed", "closed"])
async def test_every_status_is_allowed(session, enquiry, auth, status):
    assert patch({"status": status}, auth).json()["status"] == status
    await session.rollback()
    assert (await session.get(Enquiry, 1)).status == EnquiryStatus(status)


async def test_a_closed_enquiry_can_be_reopened(enquiry, auth):
    patch({"status": "closed"}, auth)
    assert patch({"status": "in_progress"}, auth).json()["status"] == "in_progress"


async def test_the_change_shows_in_the_list_filter(enquiry, auth):
    patch({"status": "completed"}, auth)
    assert client.get("/admin/enquiries?status=new", headers=auth).json()["total"] == 0
    assert client.get("/admin/enquiries?status=completed", headers=auth).json()["total"] == 1


@pytest.mark.parametrize("bad", ["archived", "", "NEW", 1, None])
async def test_bad_statuses_are_rejected(session, enquiry, auth, bad):
    assert patch({"status": bad}, auth).status_code == 422
    await session.rollback()
    assert (await session.get(Enquiry, 1)).status == EnquiryStatus.new


# --- internal notes (FR-54) -------------------------------------------------


async def test_notes_can_be_written_edited_and_cleared(enquiry, auth):
    assert patch({"internal_notes": "  Called, no answer  "}, auth).json()["internal_notes"] == "Called, no answer"
    assert patch({"internal_notes": "Spoke to client; fitting Friday"}, auth).json()["internal_notes"] == (
        "Spoke to client; fitting Friday"
    )  # replaced, not appended
    assert patch({"internal_notes": None}, auth).json()["internal_notes"] is None


async def test_status_and_notes_can_be_changed_together_or_apart(enquiry, auth):
    body = patch({"status": "contacted", "internal_notes": "Called"}, auth).json()
    assert (body["status"], body["internal_notes"]) == ("contacted", "Called")

    body = patch({"status": "in_progress"}, auth).json()
    assert (body["status"], body["internal_notes"]) == ("in_progress", "Called")  # notes untouched

    body = patch({"internal_notes": "Deposit paid"}, auth).json()
    assert (body["status"], body["internal_notes"]) == ("in_progress", "Deposit paid")  # status untouched


async def test_notes_are_staff_only_and_never_public(enquiry, auth):
    patch({"internal_notes": "Prefers calls after 5pm"}, auth)
    # The public form endpoints return only an id and a thank-you message.
    r = client.post(
        "/enquiries/contact", json={"name": "Zed Zed", "email": "z@example.com", "subject": "Hi", "message": "x"}
    )
    assert "Prefers calls" not in r.text


@pytest.mark.parametrize("bad", ["", "   ", "x" * 5001])
async def test_bad_notes_are_rejected(session, enquiry, auth, bad):
    assert patch({"internal_notes": bad}, auth).status_code == 422
    await session.rollback()
    assert (await session.get(Enquiry, 1)).internal_notes is None


# --- the client's own data is read-only ------------------------------------


@pytest.mark.parametrize(
    "field",
    ["name", "phone", "email", "message", "type", "garment_type", "quantity", "service", "created_at", "id"],
)
async def test_the_clients_own_fields_cannot_be_edited(session, enquiry, auth, field):
    assert patch({field: "changed"}, auth).status_code == 422
    await session.rollback()
    row = await session.get(Enquiry, 1)
    assert (row.name, row.phone, row.email, row.message) == (
        "Tunde Bello", "+2348031112222", "tunde@example.com", "Groomsmen set",
    )  # fmt: skip


# --- other cases ------------------------------------------------------------


async def test_the_response_is_the_full_detail_record(enquiry, auth):
    body = patch({"status": "contacted"}, auth).json()
    assert body["name"] == "Tunde Bello" and body["message"] == "Groomsmen set"
    assert "internal_notes" in body and "preferred_at" in body


async def test_an_empty_patch_changes_nothing(enquiry, auth):
    r = patch({}, auth)
    assert r.status_code == 200 and r.json()["status"] == "new"


def test_patching_a_missing_enquiry_is_404(session, auth):
    assert patch({"status": "closed"}, auth, id_=999).status_code == 404


async def test_enquiries_cannot_be_deleted_or_created_here(session, enquiry, auth):
    assert client.delete("/admin/enquiries/1", headers=auth).status_code == 405
    assert client.post("/admin/enquiries", json={"name": "X"}, headers=auth).status_code == 405
