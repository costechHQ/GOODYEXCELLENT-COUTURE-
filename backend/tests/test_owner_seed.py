import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.db.seed import seed
from app.models import AdminUser
from app.models.enums import AdminRole

PASSWORD = "a-long-test-password"


@pytest.fixture
async def session(sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


@pytest.fixture
def owner_env(monkeypatch):
    def set_(email="Owner@Example.com", password=PASSWORD):
        monkeypatch.setattr(settings, "owner_email", email)
        monkeypatch.setattr(settings, "owner_password", type(settings.owner_password)(password))

    return set_


async def count(session):
    return await session.scalar(select(func.count()).select_from(AdminUser))


# --- password hashing -------------------------------------------------------


def test_hashes_are_argon2id_and_salted():
    h1, h2 = hash_password(PASSWORD), hash_password(PASSWORD)
    assert h1.startswith("$argon2id$") and PASSWORD not in h1
    assert h1 != h2  # a fresh salt each time


def test_verify_accepts_the_right_password_only():
    h = hash_password(PASSWORD)
    assert verify_password(PASSWORD, h) is True
    assert verify_password("wrong-password!!", h) is False
    assert verify_password(PASSWORD, "not-a-hash") is False


# --- the owner seed ---------------------------------------------------------


async def test_without_variables_no_account_is_created(session):
    await seed(session)
    assert await count(session) == 0


async def test_creates_the_owner_with_a_hashed_password(session, owner_env):
    owner_env()
    await seed(session)

    owner = (await session.scalars(select(AdminUser))).one()
    assert owner.email == "owner@example.com"  # normalised
    assert owner.role == AdminRole.owner and owner.is_active
    assert owner.password_hash.startswith("$argon2id$") and PASSWORD not in owner.password_hash
    assert verify_password(PASSWORD, owner.password_hash)


async def test_running_twice_keeps_one_owner_and_does_not_reset_the_password(session, owner_env):
    owner_env()
    await seed(session)
    owner_env(password="a-different-long-password")
    await seed(session)

    assert await count(session) == 1
    owner = (await session.scalars(select(AdminUser))).one()
    assert verify_password(PASSWORD, owner.password_hash)


async def test_a_changed_email_does_not_add_a_second_owner(session, owner_env):
    owner_env()
    await seed(session)
    owner_env(email="someone-else@example.com")
    await seed(session)
    assert await count(session) == 1


async def test_a_staff_account_does_not_block_creating_the_owner(session, owner_env):
    session.add(AdminUser(email="staff@example.com", password_hash="h"))
    await session.commit()
    owner_env()
    await seed(session)
    assert await count(session) == 2


@pytest.mark.parametrize(
    ("email", "password", "message"),
    [
        ("owner@example.com", "", "both"),
        ("", PASSWORD, "both"),
        ("not-an-email", PASSWORD, "valid email"),
        ("owner@example.com", "short", "at least 12"),
    ],
)
async def test_bad_settings_stop_the_seed_and_create_nothing(session, owner_env, email, password, message):
    owner_env(email=email, password=password)
    with pytest.raises(SystemExit, match=message):
        await seed(session)
    assert await count(session) == 0


async def test_the_password_is_never_in_the_error_text(session, owner_env):
    owner_env(password="short")
    with pytest.raises(SystemExit) as exc:
        await seed(session)
    assert "short" not in str(exc.value).replace("at least 12 characters", "")
