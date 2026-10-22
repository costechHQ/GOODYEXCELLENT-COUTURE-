import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.main import app
from app import models

client = TestClient(app)


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


async def test_new_testimonials_are_hidden_by_default(session):
    session.add(models.Testimonial(client_name="Ada", quote="Great work"))
    await session.commit()
    assert (await session.get(models.Testimonial, 1)).visible is False


async def test_only_approved_testimonials_are_public(session):
    session.add_all(
        [
            models.Testimonial(client_name="Old", quote="q1", visible=True),
            models.Testimonial(client_name="Pending", quote="q2"),
            models.Testimonial(client_name="New", quote="q3", visible=True),
        ]
    )
    await session.commit()

    body = client.get("/testimonials").json()

    assert [t["client_name"] for t in body] == ["New", "Old"]  # newest first
    assert set(body[0]) == {"id", "client_name", "quote", "photo_url"}


def test_empty_list_when_nothing_is_approved(session):
    assert client.get("/testimonials").json() == []
