from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import app
from app.models import AdminUser, GalleryItem
from app.models.enums import AdminRole, GalleryCategory

client = TestClient(app)

URL = "https://cdn.example.com/senator-1.webp"
VALID = {"image_url": URL, "alt_text": "Navy senator with gold trim", "category": "senator"}


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
    """Headers for a signed-in Staff admin (Owner and Staff may both manage the gallery)."""
    admin = AdminUser(email="staff@example.com", password_hash=hash_password("x" * 12), role=AdminRole.staff)
    session.add(admin)
    await session.commit()
    return {"Authorization": f"Bearer {create_access_token(admin.id)}"}


async def add_item(session, **kw):
    item = GalleryItem(**({"image_url": URL, "category": GalleryCategory.suit, "alt_text": "alt"} | kw))
    session.add(item)
    await session.commit()
    return item.id


# --- access control (FR-51) -------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", "/admin/gallery"), ("patch", "/admin/gallery/1"), ("delete", "/admin/gallery/1")],
)
async def test_every_route_needs_a_signed_in_admin(session, method, path):
    await add_item(session)
    assert client.request(method.upper(), path, json={}).status_code == 401
    junk = {"Authorization": "Bearer junk"}
    assert client.request(method.upper(), path, json={}, headers=junk).status_code == 401


async def test_nothing_changes_without_a_token(session):
    item_id = await add_item(session)
    client.post("/admin/gallery", json=VALID)
    client.patch(f"/admin/gallery/{item_id}", json={"caption": "hacked"})
    client.delete(f"/admin/gallery/{item_id}")
    rows = (await session.scalars(select(GalleryItem))).all()
    assert [(r.id, r.caption) for r in rows] == [(item_id, None)]


async def test_an_expired_token_is_refused(session):
    admin = AdminUser(email="a@example.com", password_hash="h")
    session.add(admin)
    await session.commit()
    token = create_access_token(admin.id, expires_in=timedelta(seconds=-1))
    assert client.post("/admin/gallery", json=VALID, headers={"Authorization": f"Bearer {token}"}).status_code == 401


# --- create -----------------------------------------------------------------


async def test_create_saves_the_item_and_returns_it(session, auth):
    r = client.post("/admin/gallery", json=VALID | {"caption": " Groom's set ", "featured": True}, headers=auth)

    assert r.status_code == 201
    body = r.json()
    assert body["image_url"] == URL and body["caption"] == "Groom's set"  # trimmed
    assert body["category"] == "senator" and body["featured"] is True
    assert set(body) == {
        "id",
        "image_url",
        "caption",
        "alt_text",
        "category",
        "featured",
        "display_order",
        "created_at",
    }
    assert (await session.get(GalleryItem, body["id"])).alt_text == "Navy senator with gold trim"


async def test_a_new_item_goes_to_the_end_unless_a_position_is_given(session, auth):
    first = client.post("/admin/gallery", json=VALID, headers=auth).json()
    second = client.post("/admin/gallery", json=VALID, headers=auth).json()
    pinned = client.post("/admin/gallery", json=VALID | {"display_order": 0}, headers=auth).json()
    assert (first["display_order"], second["display_order"], pinned["display_order"]) == (0, 1, 0)


async def test_created_items_appear_in_the_public_gallery(session, auth):
    client.post("/admin/gallery", json=VALID, headers=auth)
    public = client.get("/gallery").json()
    assert [i["image_url"] for i in public] == [URL]
    assert "created_at" not in public[0] and "display_order" not in public[0]


@pytest.mark.parametrize(
    "bad",
    [
        {"image_url": "javascript:alert(1)"},
        {"image_url": "data:image/png;base64,AAAA"},
        {"image_url": "/uploads/a.webp"},
        {"image_url": "ftp://example.com/a.webp"},
        {"image_url": "https://example.com/" + "a" * 500},
        {"image_url": " "},
        {"alt_text": ""},
        {"alt_text": "   "},
        {"category": "dress"},
        {"caption": "x" * 301},
        {"display_order": -1},
        {"featured": "maybe"},
    ],
)
async def test_invalid_values_are_rejected_and_nothing_is_saved(session, auth, bad):
    assert client.post("/admin/gallery", json=VALID | bad, headers=auth).status_code == 422
    assert (await session.scalars(select(GalleryItem))).all() == []


@pytest.mark.parametrize("field", ["image_url", "alt_text", "category"])
async def test_required_fields(session, auth, field):
    payload = {k: v for k, v in VALID.items() if k != field}
    assert client.post("/admin/gallery", json=payload, headers=auth).status_code == 422


async def test_unknown_fields_are_rejected(session, auth):
    assert client.post("/admin/gallery", json=VALID | {"id": 99}, headers=auth).status_code == 422


# --- update -----------------------------------------------------------------


async def test_patch_changes_only_the_fields_sent(session, auth):
    item_id = await add_item(session, caption="old", featured=False, display_order=5)

    r = client.patch(f"/admin/gallery/{item_id}", json={"featured": True, "category": "agbada"}, headers=auth)

    assert r.status_code == 200
    assert (r.json()["featured"], r.json()["category"]) == (True, "agbada")
    assert (r.json()["caption"], r.json()["display_order"], r.json()["image_url"]) == ("old", 5, URL)


async def test_a_caption_can_be_cleared_with_null(session, auth):
    item_id = await add_item(session, caption="old")
    r = client.patch(f"/admin/gallery/{item_id}", json={"caption": None}, headers=auth)
    assert r.status_code == 200 and r.json()["caption"] is None


@pytest.mark.parametrize("field", ["image_url", "alt_text", "category", "featured", "display_order"])
async def test_required_fields_cannot_be_nulled(session, auth, field):
    item_id = await add_item(session)
    assert client.patch(f"/admin/gallery/{item_id}", json={field: None}, headers=auth).status_code == 422


@pytest.mark.parametrize("bad", [{"image_url": "javascript:x"}, {"alt_text": " "}, {"category": "dress"}, {"id": 2}])
async def test_patch_validates_like_create(session, auth, bad):
    item_id = await add_item(session)
    assert client.patch(f"/admin/gallery/{item_id}", json=bad, headers=auth).status_code == 422


async def test_an_empty_patch_changes_nothing(session, auth):
    item_id = await add_item(session, caption="keep")
    r = client.patch(f"/admin/gallery/{item_id}", json={}, headers=auth)
    assert r.status_code == 200 and r.json()["caption"] == "keep"


def test_patching_a_missing_item_is_404(session, auth):
    assert client.patch("/admin/gallery/999", json={"featured": True}, headers=auth).status_code == 404


# --- delete -----------------------------------------------------------------


async def test_delete_removes_only_that_item(session, auth):
    keep, drop = await add_item(session), await add_item(session)

    r = client.delete(f"/admin/gallery/{drop}", headers=auth)

    assert r.status_code == 204 and r.content == b""
    assert [i.id for i in (await session.scalars(select(GalleryItem))).all()] == [keep]


def test_deleting_a_missing_item_is_404(session, auth):
    assert client.delete("/admin/gallery/999", headers=auth).status_code == 404
