from app import models
from app.db.seed import seed
from app.models import GalleryItem, Service
from app.models.enums import GalleryCategory


async def test_services_list_and_detail(client, session):
    await seed(session)
    hidden = Service(title="Hidden", slug="hidden", description="x", visible=False)
    session.add(hidden)
    await session.commit()

    body = (await client.get("/api/v1/services")).json()
    assert [s["slug"] for s in body][:2] == ["senator-wear", "kaftans"]
    assert len(body) == 8  # hidden service excluded

    assert (await client.get("/api/v1/services/senator-wear")).json()["title"] == "Senator Wear"
    assert (await client.get("/api/v1/services/hidden")).status_code == 404
    assert (await client.get("/api/v1/services/missing")).status_code == 404


async def test_gallery_filters_and_pagination(client, session):
    session.add_all(
        [
            GalleryItem(image_url="a", category=GalleryCategory.senator, featured=True),
            GalleryItem(image_url="b", category=GalleryCategory.kaftan),
            GalleryItem(image_url="c", category=GalleryCategory.senator),
        ]
    )
    await session.commit()

    assert len((await client.get("/api/v1/gallery")).json()) == 3
    assert len((await client.get("/api/v1/gallery?category=senator")).json()) == 2
    assert [i["image_url"] for i in (await client.get("/api/v1/gallery?featured=true")).json()] == [
        "a"
    ]
    assert len((await client.get("/api/v1/gallery?limit=1&offset=1")).json()) == 1
    assert (await client.get("/api/v1/gallery?category=nope")).status_code == 422
    assert (await client.get("/api/v1/gallery?limit=1000")).status_code == 422


async def test_only_approved_testimonials_are_public(client, session):
    session.add_all(
        [
            models.Testimonial(client_name="Approved", quote="q", visible=True),
            models.Testimonial(client_name="Pending", quote="q", visible=False),
        ]
    )
    await session.commit()
    names = [t["client_name"] for t in (await client.get("/api/v1/testimonials")).json()]
    assert names == ["Approved"]


async def test_settings_404_until_seeded_then_exact_contacts(client, session):
    assert (await client.get("/api/v1/settings")).status_code == 404
    await seed(session)
    body = (await client.get("/api/v1/settings")).json()
    assert body["phone_numbers"] == ["+2348060036531", "+2349024662143"]
    assert body["whatsapp_link"] == "https://wa.me/2348060036531"
