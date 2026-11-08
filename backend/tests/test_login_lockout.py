from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings, settings
from app.core.security import hash_password, read_access_token
from app.db.base import Base
from app.main import app
from app.models import AdminUser

client = TestClient(app)

PASSWORD = "a-long-test-password"
WRONG = "not-the-password!!"


@pytest.fixture(autouse=True)
def jwt_on(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SecretStr("s" * 40))


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


async def add_admin(session, email="ada@example.com", active=True):
    admin = AdminUser(email=email, password_hash=hash_password(PASSWORD), is_active=active)
    session.add(admin)
    await session.commit()
    return admin


def login(password=PASSWORD, email="ada@example.com"):
    return client.post("/admin/login", json={"email": email, "password": password})


async def reload(session, admin):
    await session.refresh(admin)
    return admin


def fail(times, **kw):
    return [login(WRONG, **kw).status_code for _ in range(times)]


# --- settings ---------------------------------------------------------------


def test_defaults_and_overrides(monkeypatch):
    monkeypatch.delenv("LOGIN_MAX_FAILURES", raising=False)
    monkeypatch.delenv("LOGIN_LOCK_MINUTES", raising=False)
    s = Settings(_env_file=None)
    assert (s.login_max_failures, s.login_lock_minutes) == (5, 15)
    monkeypatch.setenv("LOGIN_MAX_FAILURES", "3")
    assert Settings(_env_file=None).login_max_failures == 3


# --- counting and locking ---------------------------------------------------


async def test_new_accounts_start_clean(session):
    admin = await add_admin(session)
    assert admin.failed_login_attempts == 0 and admin.locked_until is None


async def test_each_wrong_password_is_counted(session):
    admin = await add_admin(session)
    fail(3)
    assert (await reload(session, admin)).failed_login_attempts == 3
    assert admin.locked_until is None


async def test_the_fifth_wrong_password_locks_the_account(session):
    admin = await add_admin(session)
    assert fail(5) == [401] * 5

    await reload(session, admin)
    locked_until = admin.locked_until.replace(tzinfo=UTC)
    assert admin.failed_login_attempts == 0  # the counter restarts once a lock begins
    assert timedelta(minutes=14) < locked_until - datetime.now(UTC) <= timedelta(minutes=15)


async def test_a_good_sign_in_resets_the_counter(session):
    admin = await add_admin(session)
    fail(4)
    assert login().status_code == 200
    assert (await reload(session, admin)).failed_login_attempts == 0
    fail(4)  # four more is still under the limit, so no lock
    assert login().status_code == 200


async def test_the_limit_comes_from_settings(session, monkeypatch):
    monkeypatch.setattr(settings, "login_max_failures", 2)
    admin = await add_admin(session)
    fail(2)
    assert (await reload(session, admin)).locked_until is not None


# --- while locked -----------------------------------------------------------


async def test_a_locked_account_refuses_even_the_right_password(session):
    await add_admin(session)
    fail(5)
    r = login()
    assert r.status_code == 401 and "access_token" not in r.text


async def test_a_locked_response_is_identical_to_any_other_failure(session):
    await add_admin(session)
    wrong_before_lock = login(WRONG)
    fail(4)
    locked_right = login()
    locked_wrong = login(WRONG)
    unknown = login(email="nobody@example.com")

    responses = (wrong_before_lock, locked_right, locked_wrong, unknown)
    assert {r.status_code for r in responses} == {401}
    assert len({r.text for r in responses}) == 1  # same body
    assert len({r.headers["www-authenticate"] for r in responses}) == 1  # same headers that matter
    assert "retry-after" not in locked_right.headers  # would reveal that a lock exists


async def test_attempts_during_a_lock_neither_count_nor_extend_it(session):
    admin = await add_admin(session)
    fail(5)
    await reload(session, admin)
    locked_until = admin.locked_until

    fail(10)

    await reload(session, admin)
    assert admin.locked_until == locked_until and admin.failed_login_attempts == 0


async def test_a_locked_account_spends_a_password_check(session, monkeypatch):
    await add_admin(session)
    fail(5)
    calls = []
    monkeypatch.setattr("app.routers.admin.burn_password_check", lambda pw: calls.append(pw))
    login()
    assert calls == [PASSWORD]


async def test_locking_one_account_does_not_affect_another(session):
    await add_admin(session)
    await add_admin(session, email="staff@example.com")
    fail(5)
    assert login(email="staff@example.com").status_code == 200


# --- when the lock ends -----------------------------------------------------


async def test_the_account_works_again_once_the_lock_has_passed(session):
    admin = await add_admin(session)
    fail(5)
    await reload(session, admin)
    admin.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()

    r = login()

    assert r.status_code == 200 and read_access_token(r.json()["access_token"]) == admin.id
    await reload(session, admin)
    assert admin.locked_until is None and admin.failed_login_attempts == 0


async def test_a_wrong_password_after_a_lock_ends_starts_a_fresh_count(session):
    admin = await add_admin(session)
    fail(5)
    await reload(session, admin)
    admin.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()

    login(WRONG)

    assert (await reload(session, admin)).failed_login_attempts == 1


# --- other cases ------------------------------------------------------------


async def test_a_deactivated_account_with_the_right_password_is_refused_and_not_counted(session):
    admin = await add_admin(session, active=False)
    assert login().status_code == 401
    assert (await reload(session, admin)).failed_login_attempts == 0


async def test_unknown_emails_create_nothing_to_lock(session):
    assert fail(10, email="nobody@example.com") == [401] * 10
