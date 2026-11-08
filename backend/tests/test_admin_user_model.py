import pytest
from sqlalchemy.exc import IntegrityError, StatementError

from app.db.base import Base
from app.models import AdminUser
from app.models.enums import AdminRole


@pytest.fixture
async def session(sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


def test_roles_match_fr_57():
    assert [r.value for r in AdminRole] == ["owner", "staff"]


async def test_defaults_are_least_privilege(session):
    session.add(AdminUser(email="ada@example.com", password_hash="hash"))
    await session.commit()
    user = await session.get(AdminUser, 1)
    assert user.role == AdminRole.staff  # never an Owner by accident
    assert user.is_active is True
    assert user.created_at is not None  # filled in by the database


async def test_email_is_trimmed_and_lowercased(session):
    session.add(AdminUser(email="  Ada@Example.COM ", password_hash="hash"))
    await session.commit()
    assert (await session.get(AdminUser, 1)).email == "ada@example.com"


async def test_email_must_be_unique_whatever_the_capitalisation(session):
    session.add(AdminUser(email="ada@example.com", password_hash="h"))
    await session.commit()
    session.add(AdminUser(email="ADA@example.com", password_hash="h"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_rejects_an_unknown_role(session):
    session.add(AdminUser(email="x@example.com", password_hash="h", role="superuser"))
    with pytest.raises(StatementError):
        await session.commit()
