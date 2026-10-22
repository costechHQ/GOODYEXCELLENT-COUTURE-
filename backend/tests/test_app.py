from app import models  # noqa: F401
from app.core.security import hash_password, verify_password
from app.db.base import Base


def test_all_srs_entities_registered():
    assert set(Base.metadata.tables) == {
        "enquiries",
        "services",
        "gallery_items",
        "testimonials",
        "admin_users",
        "site_settings",
    }


def test_password_hashing_roundtrip():
    hashed = hash_password("s3cret")
    assert hashed != "s3cret"
    assert verify_password("s3cret", hashed)
    assert not verify_password("wrong", hashed)


async def test_unknown_route_404(client):
    assert (await client.get("/api/v1/nope")).status_code == 404
