import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import app
from app.models import AdminUser, Service
from app.models.enums import AdminRole

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
    """Headers for a signed-in Staff admin (Owner and Staff may both edit services)."""
    admin = AdminUser(email="staff@example.com", password_hash=hash_password("x" * 12), role=AdminRole.staff)
    session.add(admin)
    await session.commit()
    return {"Authorization": f"Bearer {create_access_token(admin.id)}"}


@pytest.fixture
async def services(session):
    session.add_all(
        [
            Service(title="Senator Wear", slug="senator-wear", description="Placeholder", display_order=1),
            Service(title="Kaftans", slug="kaftans", description="Placeholder", display_order=0),
            Service(title="Shirts", slug="shirts", description="Placeholder", display_order=2, visible=False),
        ]
    )
    await session.commit()


# --- access control (FR-51) -------------------------------------------------


@pytest.mark.parametrize("method, path", [("GET", "/admin/services"), ("PATCH", "/admin/services/1")])
async def test_every_route_needs_a_signed_in_admin(services, method, path):
    assert client.request(method, path, json={}).status_code == 401
    assert client.request(method, path, json={}, headers={"Authorization": "Bearer junk"}).status_code == 401


async def test_nothing_changes_without_a_token(session, services):
    client.patch("/admin/services/1", json={"title": "Hacked", "visible": False})
    row = await session.get(Service, 1)
    assert (row.title, row.visible) == ("Senator Wear", True)


# --- list -------------------------------------------------------------------


async def test_the_admin_list_includes_hidden_services_in_order(services, auth):
    body = client.get("/admin/services", headers=auth).json()

    assert [s["slug"] for s in body] == ["kaftans", "senator-wear", "shirts"]
    assert [s["visible"] for s in body] == [True, True, False]
    assert set(body[0]) == {"id", "title", "slug", "description", "image_url", "display_order", "visible"}


async def test_the_public_list_still_hides_hidden_services(services):
    assert [s["slug"] for s in client.get("/services").json()] == ["kaftans", "senator-wear"]


# --- update -----------------------------------------------------------------


async def test_patch_changes_only_the_fields_sent(session, services, auth):
    r = client.patch("/admin/services/1", json={"description": " Hand-cut senator suits. "}, headers=auth)

    assert r.status_code == 200
    assert r.json()["description"] == "Hand-cut senator suits."  # trimmed
    assert (r.json()["title"], r.json()["slug"], r.json()["display_order"]) == ("Senator Wear", "senator-wear", 1)


async def test_edits_show_up_on_the_public_page(services, auth):
    client.patch("/admin/services/1", json={"title": "Senator Suits", "description": "Approved copy."}, headers=auth)
    public = client.get("/services/senator-wear").json()
    assert (public["title"], public["description"]) == ("Senator Suits", "Approved copy.")
    assert "display_order" not in public and "visible" not in public


async def test_hiding_and_unhiding_a_service(services, auth):
    client.patch("/admin/services/1", json={"visible": False}, headers=auth)
    assert client.get("/services/senator-wear").status_code == 404
    client.patch("/admin/services/1", json={"visible": True}, headers=auth)
    assert client.get("/services/senator-wear").status_code == 200


async def test_the_slug_cannot_be_changed(session, services, auth):
    r = client.patch("/admin/services/1", json={"slug": "new-url"}, headers=auth)
    assert r.status_code == 422
    assert (await session.get(Service, 1)).slug == "senator-wear"


async def test_the_picture_can_be_set_and_removed(services, auth):
    url = "https://cdn.example.com/senator.webp"
    assert client.patch("/admin/services/1", json={"image_url": url}, headers=auth).json()["image_url"] == url
    assert client.patch("/admin/services/1", json={"image_url": None}, headers=auth).json()["image_url"] is None


@pytest.mark.parametrize("field", ["title", "description", "display_order", "visible"])
async def test_required_fields_cannot_be_nulled(services, auth, field):
    assert client.patch("/admin/services/1", json={field: None}, headers=auth).status_code == 422


@pytest.mark.parametrize(
    "bad",
    [
        {"title": " "},
        {"title": "x" * 161},
        {"description": ""},
        {"description": "x" * 5001},
        {"image_url": "javascript:alert(1)"},
        {"image_url": "/uploads/a.webp"},
        {"display_order": -1},
        {"visible": "maybe"},
        {"id": 5},
    ],
)
async def test_invalid_values_are_rejected_and_nothing_changes(session, services, auth, bad):
    assert client.patch("/admin/services/1", json=bad, headers=auth).status_code == 422
    row = await session.get(Service, 1)
    assert (row.title, row.description, row.image_url) == ("Senator Wear", "Placeholder", None)


async def test_an_empty_patch_changes_nothing(services, auth):
    r = client.patch("/admin/services/1", json={}, headers=auth)
    assert r.status_code == 200 and r.json()["title"] == "Senator Wear"


def test_patching_a_missing_service_is_404(session, auth):
    assert client.patch("/admin/services/999", json={"title": "Nope"}, headers=auth).status_code == 404


async def test_no_service_is_created_or_removed(session, services, auth):
    assert client.post("/admin/services", json={"title": "New"}, headers=auth).status_code == 405
    assert client.delete("/admin/services/1", headers=auth).status_code == 405
    assert len((await session.scalars(select(Service))).all()) == 3
