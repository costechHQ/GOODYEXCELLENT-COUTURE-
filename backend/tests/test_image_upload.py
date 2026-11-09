import re
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from app.core.config import settings
from app.core.images import MAX_PIXELS, process_image
from app.core.security import create_access_token, hash_password
from app.core.storage import LocalStorage
from app.db.base import Base
from app.main import app
from app.models import AdminUser
from app.models.enums import AdminRole

client = TestClient(app)
UPLOAD = "/admin/uploads/images"


# --- helpers ----------------------------------------------------------------


def make(fmt="JPEG", size=(1000, 600), color=(200, 30, 30), mode="RGB", **save_args):
    out = BytesIO()
    Image.new(mode, size, color).save(out, format=fmt, **save_args)
    return out.getvalue()


def send(data, name="photo.jpg", content_type="image/jpeg", headers=None):
    return client.post(UPLOAD, files={"file": (name, data, content_type)}, headers=headers)


def webp(data):
    image = Image.open(BytesIO(data))
    assert image.format == "WEBP"
    return image


@pytest.fixture(autouse=True)
def jwt_on(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SecretStr("s" * 40))


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    """Every test writes to its own empty folder and never to the project."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "api_public_url", "https://api.goody.example/")
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


# --- the pipeline on its own ------------------------------------------------


def test_a_large_photo_becomes_three_webp_sizes():
    result = process_image(make(size=(3000, 2000)))

    assert sorted(result.variants) == [400, 800, 1600]
    assert (result.width, result.height) == (3000, 2000)
    for width, data in result.variants.items():
        image = webp(data)
        assert image.width == width and image.height == round(2000 * width / 3000)


def test_a_medium_photo_gets_the_smaller_sizes_and_its_own_width():
    assert sorted(process_image(make(size=(1000, 500))).variants) == [400, 800, 1000]


def test_a_small_photo_is_never_enlarged():
    result = process_image(make(size=(300, 200)))
    assert list(result.variants) == [300] and webp(result.variants[300]).size == (300, 200)


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_the_three_allowed_formats_are_accepted(fmt):
    assert process_image(make(fmt=fmt)).variants


def test_transparency_survives_for_png():
    data = make(fmt="PNG", mode="RGBA", color=(255, 0, 0, 0), size=(600, 600))
    image = webp(process_image(data).variants[600])
    assert image.mode == "RGBA" and image.getpixel((10, 10))[3] == 0


def test_palette_png_with_transparency_keeps_it():
    out = BytesIO()
    Image.new("P", (500, 500)).save(out, format="PNG", transparency=0)
    assert webp(process_image(out.getvalue()).variants[500]).mode == "RGBA"


def test_cmyk_jpeg_is_converted_to_rgb():
    assert webp(process_image(make(mode="CMYK", color=(0, 0, 0, 0), size=(500, 500))).variants[500]).mode == "RGB"


def test_metadata_such_as_gps_location_is_removed():
    exif = Image.Exif()
    exif[0x010F] = "SecretCamera"  # make
    exif[0x8825] = {1: "N", 2: (6.0, 27.0, 0.0), 3: "E", 4: (7.0, 30.0, 0.0)}  # a GPS location
    original = make(size=(800, 800), exif=exif)
    assert b"SecretCamera" in original  # the test photo really carries metadata

    for data in process_image(original).variants.values():
        image = webp(data)
        assert not image.getexif() and "exif" not in image.info and "icc_profile" not in image.info
        assert b"SecretCamera" not in data and b"EXIF" not in data


def test_a_sideways_photo_is_stood_upright():
    exif = Image.Exif()
    exif[0x0112] = 6  # "rotate 90 degrees to view"
    result = process_image(make(size=(1000, 400), exif=exif))
    assert (result.width, result.height) == (400, 1000)


BAD_FILES = {
    "empty": (lambda: b"", 415),
    "text": (lambda: b"this is not an image", 415),
    "svg_with_script": (lambda: b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", 415),
    "pdf": (lambda: b"%PDF-1.7 fake", 415),
    "fake_gif_header": (lambda: b"GIF89a" + b"\x00" * 50, 415),
    "real_gif": (lambda: make(fmt="GIF", size=(50, 50)), 415),
    "real_bmp": (lambda: make(fmt="BMP", size=(50, 50)), 415),
    "real_tiff": (lambda: make(fmt="TIFF", size=(50, 50)), 415),
    "jpeg_cut_in_the_header": (lambda: make()[:200], 415),  # no readable header left: not recognisably an image
    "jpeg_cut_in_half": (lambda: make(size=(600, 400))[: len(make(size=(600, 400))) // 2], 422),  # damaged
}


@pytest.mark.parametrize("kind", BAD_FILES)
def test_other_files_are_refused(kind):
    from app.core.images import ImageRejected

    factory, status = BAD_FILES[kind]
    with pytest.raises(ImageRejected) as refused:
        process_image(factory())
    assert refused.value.status == status


def test_an_animated_image_is_refused():
    out = BytesIO()
    frames = [Image.new("RGB", (50, 50), c) for c in ((255, 0, 0), (0, 255, 0))]
    frames[0].save(out, format="WEBP", save_all=True, append_images=frames[1:], duration=100)
    from app.core.images import ImageRejected

    with pytest.raises(ImageRejected, match="Animated"):
        process_image(out.getvalue())


def test_a_decompression_bomb_is_refused_without_decoding_it():
    # A flat 30000 x 30000 picture is tiny as a file but would need gigabytes of memory to open.
    out = BytesIO()
    Image.new("1", (30_000, 30_000)).save(out, format="PNG")
    assert len(out.getvalue()) < 1_000_000 and 30_000 * 30_000 > MAX_PIXELS
    from app.core.images import ImageRejected

    with pytest.raises(ImageRejected, match="too large") as refused:
        process_image(out.getvalue())
    assert refused.value.status == 422


# --- storage ----------------------------------------------------------------

GOOD = "0123456789abcdef0123456789abcdef-800.webp"


def test_storage_saves_and_finds_only_names_it_generates(tmp_path):
    storage = LocalStorage(tmp_path / "store")
    storage.save(GOOD, b"data")
    assert storage.path_for(GOOD).read_bytes() == b"data"
    assert not list((tmp_path / "store").glob("*.part"))  # no half-written leftovers


@pytest.mark.parametrize(
    "name",
    [
        "../secret.webp",
        "..\\secret.webp",
        "/etc/passwd",
        "a.webp",
        GOOD.upper(),
        GOOD + ".exe",
        "0" * 32 + "-800.png",
        "",
    ],
)
def test_storage_refuses_unsafe_names(tmp_path, name):
    storage = LocalStorage(tmp_path / "store")
    with pytest.raises(ValueError):
        storage.save(name, b"x")
    assert storage.path_for(name) is None
    assert not (tmp_path / "secret.webp").exists()


def test_storage_delete_removes_the_file_and_ignores_missing_ones(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.save(GOOD, b"x")
    storage.delete(GOOD)
    storage.delete(GOOD)
    storage.delete("../../x")
    assert storage.path_for(GOOD) is None


# --- the upload route -------------------------------------------------------


@pytest.mark.parametrize("headers", [None, {"Authorization": "Bearer junk"}])
async def test_uploading_needs_a_signed_in_admin(session, upload_dir, headers):
    assert send(make(), headers=headers).status_code == 401
    assert not upload_dir.exists() or not list(upload_dir.iterdir())  # and nothing was written


async def test_an_upload_returns_addresses_and_saves_real_webp_files(session, auth, upload_dir):
    r = send(make(size=(3000, 2000)), headers=auth)

    assert r.status_code == 201
    body = r.json()
    assert (body["width"], body["height"]) == (3000, 2000)
    assert sorted(body["variants"], key=int) == ["400", "800", "1600"]
    assert body["url"] == body["variants"]["1600"]
    assert re.fullmatch(r"[0-9a-f]{32}", body["id"])
    assert body["url"] == f"https://api.goody.example/media/{body['id']}-1600.webp"  # absolute, one slash
    assert sorted(p.name for p in upload_dir.iterdir()) == [f"{body['id']}-{w}.webp" for w in (1600, 400, 800)]
    for path in upload_dir.iterdir():
        assert Image.open(path).format == "WEBP"


async def test_the_name_and_declared_type_of_the_file_do_not_matter(session, auth):
    # A real photo is accepted whatever it is called; a script is refused whatever it claims to be.
    assert send(make(), name="holiday.txt", content_type="text/plain", headers=auth).status_code == 201
    script = send(b"<script>alert(1)</script>", name="photo.jpg", content_type="image/jpeg", headers=auth)
    assert script.status_code == 415


async def test_the_original_file_name_is_never_used_for_storage(session, auth, upload_dir):
    r = send(make(), name="../../evil.php", headers=auth)
    assert r.status_code == 201
    assert all(re.fullmatch(r"[0-9a-f]{32}-\d+\.webp", p.name) for p in upload_dir.iterdir())
    assert "evil" not in r.text


async def test_each_upload_gets_its_own_random_id(session, auth):
    ids = {send(make(), headers=auth).json()["id"] for _ in range(3)}
    assert len(ids) == 3


async def test_the_uploaded_address_can_be_used_as_a_gallery_image(session, auth):
    url = send(make(), headers=auth).json()["url"]
    r = client.post(
        "/admin/gallery", json={"image_url": url, "alt_text": "A senator", "category": "senator"}, headers=auth
    )
    assert r.status_code == 201 and r.json()["image_url"] == url


@pytest.mark.parametrize("kind", ["text", "empty", "real_gif", "jpeg_cut_in_half", "svg_with_script"])
async def test_bad_uploads_get_a_clear_error_and_save_nothing(session, auth, upload_dir, kind):
    factory, status = BAD_FILES[kind]
    r = send(factory(), headers=auth)
    assert r.status_code == status and r.json()["detail"]
    assert not upload_dir.exists() or not list(upload_dir.iterdir())


async def test_a_file_over_the_size_limit_is_refused(session, auth, upload_dir, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 10_000)
    noisy = Image.effect_noise((600, 600), 100).convert("RGB")
    out = BytesIO()
    noisy.save(out, format="PNG")
    assert len(out.getvalue()) > 10_000

    r = send(out.getvalue(), headers=auth)

    assert r.status_code == 413 and "too large" in r.json()["detail"]
    assert not upload_dir.exists() or not list(upload_dir.iterdir())


async def test_a_file_just_under_the_limit_is_accepted(session, auth, monkeypatch):
    data = make(size=(200, 200))
    monkeypatch.setattr(settings, "max_upload_bytes", len(data))
    assert send(data, headers=auth).status_code == 201
    monkeypatch.setattr(settings, "max_upload_bytes", len(data) - 1)
    assert send(data, headers=auth).status_code == 413


async def test_a_request_with_no_file_is_rejected(session, auth):
    assert client.post(UPLOAD, headers=auth).status_code == 422
    assert client.post(UPLOAD, data={"other": "x"}, headers=auth).status_code == 422


# --- serving the files ------------------------------------------------------


async def test_uploaded_images_are_served_with_long_cache_and_safe_headers(session, auth):
    body = send(make(size=(1000, 600)), headers=auth).json()
    name = body["url"].rsplit("/", 1)[1]

    r = client.get(f"/media/{name}")

    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    assert "immutable" in r.headers["cache-control"] and "max-age=31536000" in r.headers["cache-control"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert Image.open(BytesIO(r.content)).format == "WEBP"


async def test_media_is_public_but_only_serves_our_files(session, upload_dir):
    upload_dir.mkdir(parents=True)
    (upload_dir / "notes.txt").write_text("private")
    (upload_dir.parent / "outside.webp").write_bytes(b"outside")
    for name in ("notes.txt", "..%2Foutside.webp", "%2e%2e/outside.webp", GOOD, "x" * 32 + "-800.webp"):
        assert client.get(f"/media/{name}").status_code == 404, name
    assert "private" not in client.get("/media/notes.txt").text
