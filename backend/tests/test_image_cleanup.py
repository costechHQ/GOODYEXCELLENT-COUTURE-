import logging
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.core.storage import LocalStorage, image_id_from_url
from app.db.base import Base
from app.main import app
from app.models import AdminUser, GalleryItem, Service, Testimonial
from app.models.enums import AdminRole

client = TestClient(app)
BASE = "https://api.goody.example"
ID_A = "a" * 32
ID_B = "b" * 32


@pytest.fixture(autouse=True)
def jwt_on(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SecretStr("s" * 40))


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "api_public_url", BASE + "/")  # a trailing slash must not matter
    return tmp_path / "uploads"


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


def upload(auth, size=(1000, 600)):
    """A real upload through the real route: returns its id and address."""
    out = BytesIO()
    Image.new("RGB", size, (10, 120, 60)).save(out, format="JPEG")
    r = client.post("/admin/uploads/images", files={"file": ("p.jpg", out.getvalue(), "image/jpeg")}, headers=auth)
    assert r.status_code == 201
    return r.json()


def files_of(upload_dir, image_id):
    return sorted(p.name for p in upload_dir.glob(f"{image_id}-*.webp")) if upload_dir.exists() else []


def gallery(auth, url, **extra):
    body = {"image_url": url, "alt_text": "alt", "category": "senator"} | extra
    r = client.post("/admin/gallery", json=body, headers=auth)
    assert r.status_code == 201
    return r.json()["id"]


def testimonial(auth, photo_url=None):
    r = client.post("/admin/testimonials", json={"client_name": "Ada", "quote": "Great", "photo_url": photo_url}, headers=auth)
    assert r.status_code == 201
    return r.json()["id"]


# --- recognising our own pictures ------------------------------------------


def test_only_addresses_under_our_own_media_path_count_as_ours():
    good = f"{BASE}/media/{ID_A}-1600.webp"
    assert image_id_from_url(good) == ID_A
    assert image_id_from_url(f"{BASE}/media/{ID_A}-400.webp") == ID_A


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        f"https://evil.example/media/{ID_A}-1600.webp",  # our path on somebody else's host
        f"{BASE}.evil.example/media/{ID_A}-1600.webp",  # a host that merely starts like ours
        f"http://api.goody.example/media/{ID_A}-1600.webp",  # wrong scheme
        f"{BASE}/media/{ID_A}-1600.webp?x=1",
        f"{BASE}/media/{ID_A}-1600.webp#top",
        f"{BASE}/media/{ID_A.upper()}-1600.webp",
        f"{BASE}/media/{ID_A}-1600.png",
        f"{BASE}/media/{'a' * 31}-1600.webp",
        f"{BASE}/media/../{ID_A}-1600.webp",
        f"{BASE}/media/sub/{ID_A}-1600.webp",
        f"{BASE}/other/{ID_A}-1600.webp",
        "https://cdn.example.com/photo.webp",
    ],
)
def test_everything_else_is_not_ours(url):
    assert image_id_from_url(url) is None


def test_delete_image_removes_every_size_of_that_image_only(tmp_path):
    storage = LocalStorage(tmp_path)
    for image_id in (ID_A, ID_B):
        for width in (400, 800, 1600):
            storage.save(f"{image_id}-{width}.webp", b"x")
    (tmp_path / "notes.txt").write_text("keep")

    assert storage.delete_image(ID_A) == 3

    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(["notes.txt"] + [f"{ID_B}-{w}.webp" for w in (400, 800, 1600)])


@pytest.mark.parametrize("bad", ["*", "../*", ID_A.upper(), "a" * 31, "", ID_A + "*", "[a-f]" * 6])
def test_delete_image_ignores_anything_that_is_not_a_plain_id(tmp_path, bad):
    storage = LocalStorage(tmp_path)
    storage.save(f"{ID_A}-800.webp", b"x")
    assert storage.delete_image(bad) == 0
    assert (tmp_path / f"{ID_A}-800.webp").exists()  # a wildcard cannot be used to delete other files


def test_delete_image_copes_with_a_missing_folder(tmp_path):
    assert LocalStorage(tmp_path / "nope").delete_image(ID_A) == 0


# --- gallery ----------------------------------------------------------------


async def test_deleting_a_gallery_item_deletes_its_picture_files(session, auth, upload_dir):
    pic = upload(auth)
    item = gallery(auth, pic["url"])
    assert len(files_of(upload_dir, pic["id"])) == 3

    assert client.delete(f"/admin/gallery/{item}", headers=auth).status_code == 204

    assert files_of(upload_dir, pic["id"]) == []
    assert (await session.scalars(select(GalleryItem))).all() == []


async def test_a_picture_shared_by_two_items_stays_until_the_last_one_goes(session, auth, upload_dir):
    pic = upload(auth)
    first, second = gallery(auth, pic["url"]), gallery(auth, pic["variants"]["800"])  # different sizes, same image

    client.delete(f"/admin/gallery/{first}", headers=auth)
    assert len(files_of(upload_dir, pic["id"])) == 3  # still in use

    client.delete(f"/admin/gallery/{second}", headers=auth)
    assert files_of(upload_dir, pic["id"]) == []


async def test_other_pictures_are_never_touched(session, auth, upload_dir):
    keep, drop = upload(auth), upload(auth)
    gallery(auth, keep["url"])
    item = gallery(auth, drop["url"])

    client.delete(f"/admin/gallery/{item}", headers=auth)

    assert files_of(upload_dir, drop["id"]) == [] and len(files_of(upload_dir, keep["id"])) == 3


async def test_replacing_the_picture_deletes_the_old_files_and_keeps_the_new(session, auth, upload_dir):
    old, new = upload(auth), upload(auth)
    item = gallery(auth, old["url"])

    r = client.patch(f"/admin/gallery/{item}", json={"image_url": new["url"]}, headers=auth)

    assert r.status_code == 200 and r.json()["image_url"] == new["url"]
    assert files_of(upload_dir, old["id"]) == [] and len(files_of(upload_dir, new["id"])) == 3


async def test_editing_other_fields_never_touches_the_files(session, auth, upload_dir):
    pic = upload(auth)
    item = gallery(auth, pic["url"])
    client.patch(f"/admin/gallery/{item}", json={"caption": "New", "featured": True}, headers=auth)
    client.patch(f"/admin/gallery/{item}", json={"image_url": pic["url"]}, headers=auth)  # same address again
    assert len(files_of(upload_dir, pic["id"])) == 3


async def test_a_picture_hosted_elsewhere_is_ignored(session, auth, upload_dir):
    pic = upload(auth)
    item = gallery(auth, "https://cdn.example.com/photo.webp")
    assert client.delete(f"/admin/gallery/{item}", headers=auth).status_code == 204
    assert len(files_of(upload_dir, pic["id"])) == 3


async def test_a_look_alike_address_on_another_host_cannot_delete_our_files(session, auth, upload_dir):
    pic = upload(auth)
    gallery(auth, pic["url"])  # the real user of the picture
    impostor = gallery(auth, f"https://evil.example/media/{pic['id']}-1600.webp")

    client.delete(f"/admin/gallery/{impostor}", headers=auth)

    assert len(files_of(upload_dir, pic["id"])) == 3


async def test_pointing_a_second_item_at_someone_elses_picture_does_not_expose_it_to_deletion(session, auth, upload_dir):
    pic = upload(auth)
    owner = gallery(auth, pic["url"])
    borrower = gallery(auth, pic["url"])

    client.delete(f"/admin/gallery/{borrower}", headers=auth)
    assert len(files_of(upload_dir, pic["id"])) == 3  # the original item still needs it

    client.delete(f"/admin/gallery/{owner}", headers=auth)
    assert files_of(upload_dir, pic["id"]) == []


async def test_a_picture_attached_to_a_clients_order_is_protected(session, auth, upload_dir):
    out = BytesIO()
    Image.new("RGB", (900, 600), (200, 20, 20)).save(out, format="JPEG")
    order = {"name": "Tunde Bello", "phone": "08031112222", "preferred_contact": "call", "garment_type": "Agbada"}
    assert client.post("/enquiries/order", data=order, files=[("images", ("r.jpg", out.getvalue(), "image/jpeg"))]).status_code == 201
    reference = client.get("/admin/enquiries/1", headers=auth).json()["reference_images"][0]
    image_id = reference["url"].rsplit("/", 1)[1][:32]
    assert len(files_of(upload_dir, image_id)) == 3

    borrowed = gallery(auth, reference["url"])  # an admin reuses the client's picture in the gallery...
    client.delete(f"/admin/gallery/{borrowed}", headers=auth)  # ...and then removes it again

    assert len(files_of(upload_dir, image_id)) == 3  # the client's reference picture survives


async def test_a_failed_request_deletes_nothing(session, auth, upload_dir):
    pic = upload(auth)
    item = gallery(auth, pic["url"])
    assert client.patch(f"/admin/gallery/{item}", json={"image_url": "javascript:x"}, headers=auth).status_code == 422
    assert client.patch("/admin/gallery/999", json={"image_url": "https://cdn.example.com/a.webp"}, headers=auth).status_code == 404
    assert client.delete("/admin/gallery/999", headers=auth).status_code == 404
    assert len(files_of(upload_dir, pic["id"])) == 3


async def test_nothing_is_deleted_without_signing_in(session, auth, upload_dir):
    pic = upload(auth)
    item = gallery(auth, pic["url"])
    assert client.delete(f"/admin/gallery/{item}").status_code == 401
    assert len(files_of(upload_dir, pic["id"])) == 3


async def test_a_picture_whose_files_are_already_gone_is_not_an_error(session, auth, upload_dir):
    pic = upload(auth)
    item = gallery(auth, pic["url"])
    for path in upload_dir.iterdir():
        path.unlink()
    assert client.delete(f"/admin/gallery/{item}", headers=auth).status_code == 204


async def test_a_clean_up_problem_never_fails_the_request(session, auth, upload_dir, monkeypatch, caplog):
    pic = upload(auth)
    item = gallery(auth, pic["url"])

    def disk_error(self, image_id):
        raise OSError("permission denied: /secret/path")

    monkeypatch.setattr(LocalStorage, "delete_image", disk_error)
    with caplog.at_level(logging.WARNING):
        r = client.delete(f"/admin/gallery/{item}", headers=auth)

    assert r.status_code == 204  # the item really is deleted
    assert (await session.scalars(select(GalleryItem))).all() == []
    assert "OSError" in caplog.text and "/secret/path" not in caplog.text


# --- testimonials -----------------------------------------------------------


async def test_deleting_a_testimonial_deletes_its_photo_files(session, auth, upload_dir):
    pic = upload(auth)
    client.delete(f"/admin/testimonials/{testimonial(auth, pic['url'])}", headers=auth)
    assert files_of(upload_dir, pic["id"]) == []


async def test_replacing_or_removing_a_testimonial_photo_deletes_the_old_one(session, auth, upload_dir):
    first, second = upload(auth), upload(auth)
    tid = testimonial(auth, first["url"])

    client.patch(f"/admin/testimonials/{tid}", json={"photo_url": second["url"]}, headers=auth)
    assert files_of(upload_dir, first["id"]) == [] and len(files_of(upload_dir, second["id"])) == 3

    client.patch(f"/admin/testimonials/{tid}", json={"photo_url": None}, headers=auth)
    assert files_of(upload_dir, second["id"]) == []


async def test_a_testimonial_and_a_gallery_item_can_share_a_picture(session, auth, upload_dir):
    pic = upload(auth)
    tid, item = testimonial(auth, pic["url"]), gallery(auth, pic["url"])

    client.delete(f"/admin/testimonials/{tid}", headers=auth)
    assert len(files_of(upload_dir, pic["id"])) == 3

    client.delete(f"/admin/gallery/{item}", headers=auth)
    assert files_of(upload_dir, pic["id"]) == []


async def test_a_testimonial_without_a_photo_deletes_cleanly(session, auth):
    assert client.delete(f"/admin/testimonials/{testimonial(auth)}", headers=auth).status_code == 204
    assert (await session.scalars(select(Testimonial))).all() == []


# --- services ---------------------------------------------------------------


async def test_replacing_or_removing_a_service_picture_deletes_the_old_one(session, auth, upload_dir):
    session.add(Service(title="Senator Wear", slug="senator-wear", description="d"))
    await session.commit()
    first, second = upload(auth), upload(auth)

    client.patch("/admin/services/1", json={"image_url": first["url"]}, headers=auth)
    client.patch("/admin/services/1", json={"image_url": second["url"]}, headers=auth)
    assert files_of(upload_dir, first["id"]) == [] and len(files_of(upload_dir, second["id"])) == 3

    client.patch("/admin/services/1", json={"image_url": None}, headers=auth)
    assert files_of(upload_dir, second["id"]) == []


async def test_a_service_picture_shared_with_the_gallery_is_kept(session, auth, upload_dir):
    session.add(Service(title="Kaftans", slug="kaftans", description="d"))
    await session.commit()
    pic = upload(auth)
    gallery(auth, pic["url"])
    client.patch("/admin/services/1", json={"image_url": pic["url"]}, headers=auth)

    client.patch("/admin/services/1", json={"image_url": None}, headers=auth)

    assert len(files_of(upload_dir, pic["id"])) == 3  # the gallery item still shows it
    assert (await session.get(Service, 1)).image_url is None
