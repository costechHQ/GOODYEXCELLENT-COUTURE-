import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import app
from app.models import AdminUser, Testimonial
from app.models.enums import AdminRole

client = TestClient(app)

VALID = {"client_name": "Chief Okafor", "quote": "The agbada fitted perfectly."}


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
    """Headers for a signed-in Staff admin (Owner and Staff may both manage testimonials)."""
    admin = AdminUser(email="staff@example.com", password_hash=hash_password("x" * 12), role=AdminRole.staff)
    session.add(admin)
    await session.commit()
    return {"Authorization": f"Bearer {create_access_token(admin.id)}"}


async def add(session, **kw):
    t = Testimonial(**({"client_name": "Ada", "quote": "Lovely work"} | kw))
    session.add(t)
    await session.commit()
    return t.id


# --- access control (FR-51) -------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/admin/testimonials"),
        ("POST", "/admin/testimonials"),
        ("PATCH", "/admin/testimonials/1"),
        ("DELETE", "/admin/testimonials/1"),
    ],
)
async def test_every_route_needs_a_signed_in_admin(session, method, path):
    await add(session)
    assert client.request(method, path, json={}).status_code == 401
    assert client.request(method, path, json={}, headers={"Authorization": "Bearer junk"}).status_code == 401


async def test_nothing_changes_without_a_token(session):
    tid = await add(session, visible=False)
    client.post("/admin/testimonials", json=VALID | {"visible": True})
    client.patch(f"/admin/testimonials/{tid}", json={"visible": True})
    client.delete(f"/admin/testimonials/{tid}")
    rows = (await session.scalars(select(Testimonial))).all()
    assert [(r.id, r.visible) for r in rows] == [(tid, False)]


# --- list -------------------------------------------------------------------


async def test_the_admin_list_includes_hidden_testimonials_newest_first(session, auth):
    await add(session, client_name="Old", visible=True)
    await add(session, client_name="Pending")
    await add(session, client_name="New", visible=True)

    body = client.get("/admin/testimonials", headers=auth).json()

    assert [t["client_name"] for t in body] == ["New", "Pending", "Old"]
    assert [t["visible"] for t in body] == [True, False, True]
    assert set(body[0]) == {"id", "client_name", "quote", "photo_url", "visible", "created_at"}


async def test_the_public_list_still_shows_approved_ones_only(session, auth):
    await add(session, client_name="Shown", visible=True)
    await add(session, client_name="Hidden")
    assert [t["client_name"] for t in client.get("/testimonials").json()] == ["Shown"]


# --- create -----------------------------------------------------------------


async def test_a_new_testimonial_is_hidden_until_approved(session, auth):
    r = client.post("/admin/testimonials", json=VALID, headers=auth)

    assert r.status_code == 201
    assert r.json()["visible"] is False and r.json()["created_at"]
    assert client.get("/testimonials").json() == []  # not public yet (FR-49, CR-03)
    assert (await session.get(Testimonial, r.json()["id"])).quote == "The agbada fitted perfectly."


async def test_it_can_be_published_straight_away_when_asked(session, auth):
    client.post("/admin/testimonials", json=VALID | {"visible": True}, headers=auth)
    assert [t["client_name"] for t in client.get("/testimonials").json()] == ["Chief Okafor"]


async def test_text_is_trimmed_and_the_photo_is_optional(session, auth):
    photo = "https://cdn.example.com/ada.webp"
    body = client.post(
        "/admin/testimonials",
        json={"client_name": "  Ada  ", "quote": "  Great  ", "photo_url": photo},
        headers=auth,
    ).json()
    assert (body["client_name"], body["quote"], body["photo_url"]) == ("Ada", "Great", photo)


@pytest.mark.parametrize("field", ["client_name", "quote"])
async def test_required_fields(session, auth, field):
    payload = {k: v for k, v in VALID.items() if k != field}
    assert client.post("/admin/testimonials", json=payload, headers=auth).status_code == 422


@pytest.mark.parametrize(
    "bad",
    [
        {"client_name": " "},
        {"client_name": "A"},
        {"client_name": "x" * 121},
        {"quote": ""},
        {"quote": "x" * 2001},
        {"photo_url": "javascript:alert(1)"},
        {"photo_url": "/uploads/a.webp"},
        {"visible": "maybe"},
        {"id": 5},
        {"created_at": "2020-01-01T00:00:00Z"},
    ],
)
async def test_invalid_values_are_rejected_and_nothing_is_saved(session, auth, bad):
    assert client.post("/admin/testimonials", json=VALID | bad, headers=auth).status_code == 422
    assert (await session.scalars(select(Testimonial))).all() == []


# --- update -----------------------------------------------------------------


async def test_patch_changes_only_the_fields_sent(session, auth):
    tid = await add(session, client_name="Ada", quote="Lovely work")
    r = client.patch(f"/admin/testimonials/{tid}", json={"quote": " Even better "}, headers=auth)
    assert r.status_code == 200
    assert (r.json()["client_name"], r.json()["quote"], r.json()["visible"]) == ("Ada", "Even better", False)


async def test_approving_and_hiding_a_testimonial(session, auth):
    tid = await add(session, client_name="Ada")
    client.patch(f"/admin/testimonials/{tid}", json={"visible": True}, headers=auth)
    assert [t["client_name"] for t in client.get("/testimonials").json()] == ["Ada"]
    client.patch(f"/admin/testimonials/{tid}", json={"visible": False}, headers=auth)
    assert client.get("/testimonials").json() == []


async def test_the_photo_can_be_set_and_removed(session, auth):
    tid = await add(session)
    url = "https://cdn.example.com/ada.webp"
    assert client.patch(f"/admin/testimonials/{tid}", json={"photo_url": url}, headers=auth).json()["photo_url"] == url
    assert (
        client.patch(f"/admin/testimonials/{tid}", json={"photo_url": None}, headers=auth).json()["photo_url"] is None
    )


@pytest.mark.parametrize("field", ["client_name", "quote", "visible"])
async def test_required_fields_cannot_be_nulled(session, auth, field):
    tid = await add(session)
    assert client.patch(f"/admin/testimonials/{tid}", json={field: None}, headers=auth).status_code == 422


@pytest.mark.parametrize("bad", [{"client_name": " "}, {"quote": ""}, {"photo_url": "data:x"}, {"id": 2}])
async def test_patch_validates_like_create(session, auth, bad):
    tid = await add(session)
    assert client.patch(f"/admin/testimonials/{tid}", json=bad, headers=auth).status_code == 422


async def test_an_empty_patch_changes_nothing(session, auth):
    tid = await add(session, client_name="Keep")
    r = client.patch(f"/admin/testimonials/{tid}", json={}, headers=auth)
    assert r.status_code == 200 and r.json()["client_name"] == "Keep"


def test_patching_a_missing_testimonial_is_404(session, auth):
    assert client.patch("/admin/testimonials/999", json={"visible": True}, headers=auth).status_code == 404


# --- delete -----------------------------------------------------------------


async def test_delete_removes_only_that_testimonial(session, auth):
    keep, drop = await add(session, client_name="Keep"), await add(session, client_name="Drop")

    r = client.delete(f"/admin/testimonials/{drop}", headers=auth)

    assert r.status_code == 204 and r.content == b""
    assert [t.id for t in (await session.scalars(select(Testimonial))).all()] == [keep]


async def test_a_deleted_testimonial_leaves_the_public_page(session, auth):
    tid = await add(session, visible=True)
    client.delete(f"/admin/testimonials/{tid}", headers=auth)
    assert client.get("/testimonials").json() == []


def test_deleting_a_missing_testimonial_is_404(session, auth):
    assert client.delete("/admin/testimonials/999", headers=auth).status_code == 404
