from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core import security
from app.core.auth import require_owner
from app.core.config import Settings, settings
from app.core.security import create_access_token, hash_password, read_access_token
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import AdminUser
from app.models.enums import AdminRole

client = TestClient(app)

SECRET = "s" * 40
PASSWORD = "a-long-test-password"


@pytest.fixture
def jwt_on(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SecretStr(SECRET))


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


async def add_admin(session, email="ada@example.com", role=AdminRole.staff, active=True):
    admin = AdminUser(email=email, password_hash=hash_password(PASSWORD), role=role, is_active=active)
    session.add(admin)
    await session.commit()
    return admin


def login(email="ada@example.com", password=PASSWORD):
    return client.post("/admin/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# --- settings ---------------------------------------------------------------


def test_there_is_no_default_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("ACCESS_TOKEN_MINUTES", raising=False)
    s = Settings(_env_file=None)
    assert s.jwt_secret.get_secret_value() == "" and s.access_token_minutes == 60
    assert SECRET not in repr(Settings(_env_file=None, jwt_secret=SECRET))


# --- tokens -----------------------------------------------------------------


def test_a_fresh_token_round_trips(jwt_on):
    assert read_access_token(create_access_token(42)) == 42


def test_an_expired_token_is_refused(jwt_on):
    assert read_access_token(create_access_token(1, expires_in=timedelta(seconds=-1))) is None


def test_a_token_signed_with_another_secret_is_refused(jwt_on):
    forged = jwt.encode({"sub": "1", "exp": datetime.now(UTC) + timedelta(hours=1)}, "x" * 40, algorithm="HS256")
    assert read_access_token(forged) is None


def test_an_unsigned_alg_none_token_is_refused(jwt_on):
    unsigned = jwt.encode({"sub": "1", "exp": datetime.now(UTC) + timedelta(hours=1)}, None, algorithm="none")
    assert read_access_token(unsigned) is None


def test_a_token_without_expiry_is_refused(jwt_on):
    assert read_access_token(jwt.encode({"sub": "1"}, SECRET, algorithm="HS256")) is None


@pytest.mark.parametrize("junk", ["", "abc", "a.b.c", "Bearer x"])
def test_garbage_is_refused(jwt_on, junk):
    assert read_access_token(junk) is None


def test_a_short_secret_counts_as_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SecretStr("short"))
    assert security.jwt_configured() is False


# --- login ------------------------------------------------------------------


async def test_correct_credentials_return_a_bearer_token(session, jwt_on):
    admin = await add_admin(session)
    r = login()

    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600
    assert read_access_token(body["access_token"]) == admin.id


async def test_email_is_matched_whatever_the_capitalisation(session, jwt_on):
    await add_admin(session)
    assert login(email="ADA@Example.com").status_code == 200


async def test_the_token_holds_no_role_or_personal_data(session, jwt_on):
    await add_admin(session, role=AdminRole.owner)
    claims = jwt.decode(login().json()["access_token"], SECRET, algorithms=["HS256"])
    assert set(claims) == {"sub", "iat", "exp"}


async def test_every_failure_gives_the_same_401(session, jwt_on):
    await add_admin(session)
    await add_admin(session, email="gone@example.com", active=False)

    wrong_password = login(password="not-the-password")
    unknown_email = login(email="nobody@example.com")
    deactivated = login(email="gone@example.com")

    for r in (wrong_password, unknown_email, deactivated):
        assert r.status_code == 401
        assert r.headers["www-authenticate"] == "Bearer"
    assert wrong_password.json() == unknown_email.json() == deactivated.json()


async def test_an_unknown_email_still_spends_a_password_check(session, jwt_on, monkeypatch):
    calls = []
    monkeypatch.setattr("app.routers.admin.burn_password_check", lambda pw: calls.append(pw))
    login(email="nobody@example.com")
    assert calls == [PASSWORD]


def test_login_is_unavailable_without_a_secret(session, monkeypatch):
    # Blank the secret explicitly: a developer's own .env may define one.
    monkeypatch.setattr(settings, "jwt_secret", SecretStr(""))
    r = login()
    assert r.status_code == 503 and "access_token" not in r.text


@pytest.mark.parametrize("payload", [{}, {"email": "ada@example.com"}, {"email": "bad", "password": "x"}])
def test_malformed_login_requests_are_rejected(session, jwt_on, payload):
    assert client.post("/admin/login", json=payload).status_code == 422


# --- the protected route ----------------------------------------------------


async def test_me_returns_the_signed_in_admin_without_the_hash(session, jwt_on):
    await add_admin(session, role=AdminRole.owner)
    r = client.get("/admin/me", headers=bearer(login().json()["access_token"]))

    assert r.status_code == 200
    assert set(r.json()) == {"id", "email", "role", "created_at"}
    assert r.json()["email"] == "ada@example.com" and r.json()["role"] == "owner"


def test_me_needs_a_token(session, jwt_on):
    r = client.get("/admin/me")
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("token", ["garbage", "a.b.c"])
def test_me_refuses_bad_tokens(session, jwt_on, token):
    assert client.get("/admin/me", headers=bearer(token)).status_code == 401


async def test_me_refuses_an_expired_token(session, jwt_on):
    admin = await add_admin(session)
    token = create_access_token(admin.id, expires_in=timedelta(seconds=-5))
    assert client.get("/admin/me", headers=bearer(token)).status_code == 401


async def test_deactivating_an_admin_cuts_off_a_token_that_is_still_valid(session, jwt_on):
    admin = await add_admin(session)
    token = login().json()["access_token"]
    assert client.get("/admin/me", headers=bearer(token)).status_code == 200

    admin.is_active = False
    await session.commit()

    assert client.get("/admin/me", headers=bearer(token)).status_code == 401


async def test_a_token_for_a_deleted_admin_is_refused(session, jwt_on):
    assert client.get("/admin/me", headers=bearer(create_access_token(999))).status_code == 401


def test_tokens_are_refused_when_the_secret_is_removed(session, jwt_on, monkeypatch):
    token = create_access_token(1)
    monkeypatch.setattr(settings, "jwt_secret", SecretStr(""))
    assert client.get("/admin/me", headers=bearer(token)).status_code == 401


# --- the owner-only guard ---------------------------------------------------


@pytest.fixture
def owner_only_client(use_database):
    probe = FastAPI()
    probe.dependency_overrides[get_session] = app.dependency_overrides[get_session]

    @probe.get("/owner-only", dependencies=[Depends(require_owner)])
    async def owner_only():
        return {"ok": True}

    return TestClient(probe)


async def test_owner_routes_admit_owners_and_refuse_staff(session, jwt_on, owner_only_client):
    owner = await add_admin(session, email="owner@example.com", role=AdminRole.owner)
    staff = await add_admin(session, email="staff@example.com", role=AdminRole.staff)

    ok = owner_only_client.get("/owner-only", headers=bearer(create_access_token(owner.id)))
    forbidden = owner_only_client.get("/owner-only", headers=bearer(create_access_token(staff.id)))
    anonymous = owner_only_client.get("/owner-only")

    assert (ok.status_code, forbidden.status_code, anonymous.status_code) == (200, 403, 401)
