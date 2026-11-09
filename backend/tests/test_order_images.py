import re
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr
from sqlalchemy import select

from app.core import mail
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.core.storage import LocalStorage
from app.db.base import Base
from app.main import app
from app.models import AdminUser, Enquiry, EnquiryImage
from app.models.enums import AdminRole
from app.routers import enquiries

client = TestClient(app)
ORDER = "/enquiries/order"
FIELDS = {"name": "Tunde Bello", "phone": "08031112222", "preferred_contact": "call", "garment_type": "Agbada"}


# --- helpers ----------------------------------------------------------------


def photo(size=(1200, 800), fmt="JPEG", **save_args):
    out = BytesIO()
    Image.new("RGB", size, (30, 90, 160)).save(out, format=fmt, **save_args)
    return out.getvalue()


def attach(*pictures):
    """Files for a multipart request: the browser field is called `images`, repeated for each file."""
    return [("images", (f"ref{n}.jpg", data, "image/jpeg")) for n, data in enumerate(pictures, 1)]


def order(fields=None, files=None, **kw):
    return client.post(ORDER, data=FIELDS | (fields or {}), files=files, **kw)


@pytest.fixture(autouse=True)
def jwt_on(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SecretStr("s" * 40))


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "api_public_url", "https://api.goody.example")
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


def files_on_disk(upload_dir):
    return sorted(p.name for p in upload_dir.iterdir()) if upload_dir.exists() else []


async def nothing_saved(session, upload_dir):
    assert (await session.scalars(select(Enquiry))).all() == []
    assert (await session.scalars(select(EnquiryImage))).all() == []
    assert files_on_disk(upload_dir) == []


# --- the happy path ---------------------------------------------------------


async def test_an_order_with_no_pictures_still_works(session, upload_dir):
    r = order()
    assert r.status_code == 201 and set(r.json()) == {"id", "message"}
    assert (await session.scalars(select(EnquiryImage))).all() == []
    assert files_on_disk(upload_dir) == []


async def test_pictures_are_saved_with_the_enquiry(session, upload_dir):
    r = order(files=attach(photo(), photo(size=(3000, 2000))))

    assert r.status_code == 201
    enquiry = (await session.scalars(select(Enquiry))).one()
    rows = (await session.scalars(select(EnquiryImage).order_by(EnquiryImage.id))).all()
    assert [row.enquiry_id for row in rows] == [enquiry.id, enquiry.id]
    assert [(row.width, row.height) for row in rows] == [(1200, 800), (3000, 2000)]
    assert rows[1].widths == [400, 800, 1600]
    names = files_on_disk(upload_dir)
    assert len(names) == 3 + 3 and all(
        re.fullmatch(r"[0-9a-f]{32}-\d+\.webp", n) for n in names
    )  # 1200 gives 400, 800, 1200 too
    for name in names:
        assert Image.open(upload_dir / name).format == "WEBP"


async def test_up_to_five_pictures_are_allowed(session):
    assert order(files=attach(*[photo(size=(300, 300))] * 5)).status_code == 201
    assert len((await session.scalars(select(EnquiryImage))).all()) == 5


async def test_the_text_fields_are_still_validated_and_normalised(session):
    order(files=attach(photo()))
    enquiry = (await session.scalars(select(Enquiry))).one()
    assert enquiry.phone == "+2348031112222" and enquiry.garment_type == "Agbada"


@pytest.mark.parametrize("blank", ["", "   "])
async def test_blank_optional_form_fields_count_as_not_provided(session, blank):
    blanks = {k: blank for k in ("email", "occasion", "needed_by", "quantity", "fabric_preference", "message")}
    assert order(blanks).status_code == 201
    enquiry = (await session.scalars(select(Enquiry))).one()
    assert (enquiry.email, enquiry.occasion, enquiry.needed_by, enquiry.quantity) == (None, None, None, None)


async def test_a_browser_with_no_file_chosen_sends_an_empty_part_which_is_ignored(session, upload_dir):
    # This is exactly what a browser sends for an empty <input type="file" multiple>.
    r = order(files=[("images", ("", b"", "application/octet-stream"))])
    assert r.status_code == 201 and files_on_disk(upload_dir) == []
    assert len((await session.scalars(select(Enquiry))).all()) == 1


async def test_an_empty_part_next_to_real_pictures_is_ignored(session):
    files = attach(photo(size=(300, 300))) + [("images", ("", b"", "application/octet-stream"))]
    assert order(files=files).status_code == 201
    assert len((await session.scalars(select(EnquiryImage))).all()) == 1


async def test_text_sent_in_the_files_field_is_refused(session, upload_dir):
    r = client.post(ORDER, data=FIELDS | {"images": "not a file"})
    assert r.status_code == 422 and "must be files" in r.json()["detail"]
    await nothing_saved(session, upload_dir)


# --- all or nothing ---------------------------------------------------------


async def test_a_sixth_picture_is_refused_and_nothing_is_saved(session, upload_dir):
    r = order(files=attach(*[photo(size=(200, 200))] * 6))
    assert r.status_code == 422 and "up to 5" in r.json()["detail"]
    await nothing_saved(session, upload_dir)


@pytest.mark.parametrize(
    ("bad", "status", "words"),
    [
        (b"<script>alert(1)</script>", 415, "JPEG, PNG or WebP"),
        (b"", 415, "JPEG, PNG or WebP"),
        (photo(size=(600, 400))[:2500], 422, "damaged"),
    ],
)
async def test_one_bad_picture_means_no_enquiry_and_no_files(session, upload_dir, bad, status, words):
    r = order(files=attach(photo(), bad, photo()))  # the bad one is the second of three
    assert r.status_code == status
    assert r.json()["detail"].startswith("Reference image 2: ") and words in r.json()["detail"]
    await nothing_saved(session, upload_dir)


async def test_a_picture_over_the_size_limit_is_refused_and_named(session, upload_dir, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 20_000)  # the whole request may be up to ~228 KB
    noisy = BytesIO()
    Image.effect_noise((150, 150), 100).convert("RGB").save(noisy, format="PNG")
    assert 20_000 < len(noisy.getvalue()) < 100_000  # over the per-picture limit, under the request limit

    r = order(files=attach(photo(size=(100, 100)), noisy.getvalue()))

    assert r.status_code == 413 and r.json()["detail"].startswith("Reference image 2: That file is too large")
    await nothing_saved(session, upload_dir)


async def test_the_public_form_is_stricter_about_pixels_than_the_admin_area(session, upload_dir, auth):
    big = photo(size=(4500, 4500), quality=1)  # about 20 megapixels but a tiny file
    assert 16_000_000 < 4500 * 4500 < 40_000_000 and len(big) < 500_000

    refused = order(files=attach(big))

    assert refused.status_code == 422 and "under 16 megapixels" in refused.json()["detail"]
    await nothing_saved(session, upload_dir)
    admin = client.post("/admin/uploads/images", files={"file": ("big.jpg", big, "image/jpeg")}, headers=auth)
    assert admin.status_code == 201  # the same picture is fine for a signed-in admin


async def test_a_database_failure_removes_the_files_that_were_written(session, upload_dir, monkeypatch):
    async def database_down(*args, **kwargs):
        raise RuntimeError("database down")

    monkeypatch.setattr(enquiries, "_save", database_down)
    quiet = TestClient(app, raise_server_exceptions=False)

    r = quiet.post(ORDER, data=FIELDS, files=attach(photo(), photo()))

    assert r.status_code == 500
    assert files_on_disk(upload_dir) == []  # no orphans
    assert (await session.scalars(select(Enquiry))).all() == []


async def test_a_storage_failure_halfway_removes_what_was_written(session, upload_dir, monkeypatch):
    real_save, calls = LocalStorage.save, []

    def flaky(self, name, data):
        calls.append(name)
        if len(calls) == 2:
            raise OSError("disk full")
        real_save(self, name, data)

    monkeypatch.setattr(LocalStorage, "save", flaky)

    r = order(files=attach(photo()))

    assert r.status_code == 500 and "could not be saved" in r.json()["detail"]
    await nothing_saved(session, upload_dir)


# --- spam and abuse ---------------------------------------------------------


async def test_a_bot_gets_a_normal_answer_but_no_image_is_ever_processed(session, upload_dir):
    corrupt = b"this would be refused if anyone looked at it"
    r = order({"website": "http://spam.example"}, files=attach(corrupt))
    assert r.status_code == 201 and r.json()["id"] == 0  # a refusal would have told the bot it was caught
    await nothing_saved(session, upload_dir)


async def test_the_order_form_shares_the_per_visitor_rate_limit(session):
    for _ in range(10):
        assert order().status_code == 201
    assert order(files=attach(photo(size=(100, 100)))).status_code == 429


async def test_unknown_form_fields_and_staff_fields_are_rejected(session, upload_dir):
    for extra in ({"status": "closed"}, {"internal_notes": "x"}, {"type": "laundry"}, {"id": "5"}):
        assert order(extra, files=attach(photo())).status_code == 422
    await nothing_saved(session, upload_dir)


async def test_a_json_order_is_no_longer_accepted(session):
    assert client.post(ORDER, json=FIELDS).status_code == 422


async def test_text_errors_are_reported_before_any_picture_is_processed(session, upload_dir):
    r = order({"phone": "12345"}, files=attach(photo()))
    assert r.status_code == 422 and "phone" in r.text
    await nothing_saved(session, upload_dir)


# --- the request-size guard -------------------------------------------------


async def test_an_oversized_request_is_refused_before_it_is_read(session, upload_dir, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 1_000)  # limit: 5 x 1 KB + 128 KB of allowance
    r = client.post(ORDER, data=FIELDS, files=attach(b"x" * 300_000))
    assert r.status_code == 413 and r.json() == {"detail": "That upload is too large."}
    await nothing_saved(session, upload_dir)


async def test_the_size_guard_also_protects_the_admin_upload_route(session, auth, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 1_000)
    r = client.post("/admin/uploads/images", files={"file": ("a.jpg", b"x" * 300_000, "image/jpeg")}, headers=auth)
    assert r.status_code == 413 and r.json() == {"detail": "That upload is too large."}  # the guard's own wording


async def test_the_size_guard_leaves_other_routes_alone(session, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 1_000)
    body = {"name": "Ada Obi", "email": "ada@example.com", "subject": "Hello", "message": "x" * 1900}
    assert client.post("/enquiries/contact", json=body).status_code == 201


async def test_the_refusal_still_carries_cors_headers(session, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 1_000)
    origin = settings.cors_origins[0]
    r = client.post(ORDER, data=FIELDS, files=attach(b"x" * 300_000), headers={"Origin": origin})
    assert r.json() == {"detail": "That upload is too large."}  # from the guard, not from the route
    assert r.status_code == 413 and r.headers["access-control-allow-origin"] == origin  # so the page can read the error


# --- what staff see ---------------------------------------------------------


async def test_the_admin_detail_lists_the_pictures_with_working_addresses(session, auth):
    order(files=attach(photo(size=(2000, 1000))))

    body = client.get("/admin/enquiries/1", headers=auth).json()

    (image,) = body["reference_images"]
    assert set(image) == {"url", "variants", "width", "height"}
    assert (image["width"], image["height"]) == (2000, 1000)
    assert sorted(image["variants"], key=int) == ["400", "800", "1600"]
    assert image["url"] == image["variants"]["1600"] and image["url"].startswith("https://api.goody.example/media/")
    served = client.get("/media/" + image["url"].rsplit("/", 1)[1])
    assert served.status_code == 200 and Image.open(BytesIO(served.content)).format == "WEBP"


async def test_an_order_without_pictures_shows_an_empty_list(session, auth):
    order()
    assert client.get("/admin/enquiries/1", headers=auth).json()["reference_images"] == []


async def test_updating_status_keeps_showing_the_pictures(session, auth):
    order(files=attach(photo()))
    body = client.patch("/admin/enquiries/1", json={"status": "contacted"}, headers=auth).json()
    assert body["status"] == "contacted" and len(body["reference_images"]) == 1


async def test_the_list_is_unchanged_and_does_not_load_pictures(session, auth):
    order(files=attach(photo()))
    item = client.get("/admin/enquiries", headers=auth).json()["items"][0]
    assert "reference_images" not in item


async def test_other_enquiries_never_show_someone_elses_pictures(session, auth):
    order(files=attach(photo()))
    order({"name": "Second Client"})
    assert len(client.get("/admin/enquiries/1", headers=auth).json()["reference_images"]) == 1
    assert client.get("/admin/enquiries/2", headers=auth).json()["reference_images"] == []


async def test_pictures_cannot_be_reached_without_knowing_their_random_name(session, auth):
    order(files=attach(photo()))
    assert client.get("/media/" + "0" * 32 + "-800.webp").status_code == 404
    assert client.get("/media/").status_code in (404, 405)


async def test_gps_metadata_in_a_clients_photo_is_not_kept(session, upload_dir):
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (6.0, 27.0, 0.0), 3: "E", 4: (7.0, 30.0, 0.0)}  # the client's home
    exif[0x010F] = "SecretCamera"
    original = photo(exif=exif)
    assert b"SecretCamera" in original

    order(files=attach(original))

    for name in files_on_disk(upload_dir):
        data = (upload_dir / name).read_bytes()
        assert b"SecretCamera" not in data and not Image.open(BytesIO(data)).getexif()


# --- the notification email -------------------------------------------------


async def test_the_alert_email_mentions_how_many_pictures_came_with_the_order(session, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "enquiry_notify_to", "orders@goody.test")
    sent = []
    monkeypatch.setattr(mail, "_send", sent.append)

    order(files=attach(photo(size=(200, 200)), photo(size=(200, 200))))
    order({"name": "No Pictures"})

    assert "Reference images: 2 (see the admin area)" in sent[0].get_content()
    assert "Reference images" not in sent[1].get_content()
