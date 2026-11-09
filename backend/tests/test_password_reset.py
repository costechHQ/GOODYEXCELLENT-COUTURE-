import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

from app.core import mail
from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    hash_reset_token,
    new_reset_token,
    read_access_claims,
    verify_password,
)
from app.db.base import Base
from app.main import app
from app.models import AdminUser, PasswordResetToken
from app.models.enums import AdminRole

client = TestClient(app)

OLD_PASSWORD = "the-old-password-1"
NEW_PASSWORD = "a-brand-new-password"
SECRET = "s" * 40
REQUEST = "/admin/password-reset/request"
CONFIRM = "/admin/password-reset/confirm"
LINK_TOKEN = re.compile(r"#token=([\w-]+)")


@pytest.fixture(autouse=True)
def jwt_on(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SecretStr(SECRET))


@pytest.fixture
def outbox(monkeypatch):
    """Mail is configured, and every message that would be sent is captured instead."""
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "mail_from", "website@goody.test")
    monkeypatch.setattr(settings, "frontend_url", "https://goody.example/")
    sent = []
    monkeypatch.setattr(mail, "_send", sent.append)
    return sent


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


async def add_admin(session, email="ada@example.com", active=True, role=AdminRole.staff, **kw):
    admin = AdminUser(email=email, password_hash=hash_password(OLD_PASSWORD), is_active=active, role=role, **kw)
    session.add(admin)
    await session.commit()
    return admin


async def add_token(session, admin, *, minutes=30, used=False):
    token, token_hash = new_reset_token()
    now = datetime.now(UTC)
    session.add(
        PasswordResetToken(
            admin_id=admin.id,
            token_hash=token_hash,
            expires_at=now + timedelta(minutes=minutes),
            used_at=now if used else None,
        )
    )
    await session.commit()
    return token


def request_reset(email="ada@example.com"):
    return client.post(REQUEST, json={"email": email})


def confirm(token, password=NEW_PASSWORD):
    return client.post(CONFIRM, json={"token": token, "new_password": password})


def login(password, email="ada@example.com"):
    return client.post("/admin/login", json={"email": email, "password": password})


def token_from(message):
    return LINK_TOKEN.search(message.get_content()).group(1)


# --- helpers ----------------------------------------------------------------


def test_reset_tokens_are_random_and_hashed_with_sha256():
    (t1, h1), (t2, h2) = new_reset_token(), new_reset_token()
    assert t1 != t2 and h1 != h2 and len(t1) >= 40
    assert h1 == hash_reset_token(t1) == hashlib.sha256(t1.encode()).hexdigest() and t1 not in h1


def test_access_claims_need_an_issue_time():
    no_iat = jwt.encode({"sub": "1", "exp": datetime.now(UTC) + timedelta(hours=1)}, SECRET, algorithm="HS256")
    assert read_access_claims(no_iat) is None
    sub, iat = read_access_claims(create_access_token(7))
    assert sub == 7 and abs(iat - int(datetime.now(UTC).timestamp())) <= 2


# --- asking for a reset -----------------------------------------------------


async def test_a_known_admin_is_emailed_a_one_time_link(session, outbox):
    await add_admin(session)

    r = request_reset()

    assert r.status_code == 202
    (msg,) = outbox
    assert msg["To"] == "ada@example.com" and msg["From"] == "website@goody.test"
    assert msg["Subject"] == "Reset your GOODYEXCELLENT COUTURE admin password"
    body = msg.get_content()
    assert "https://goody.example/admin/reset-password#token=" in body  # fragment: never sent to servers
    assert "30 minutes" in body and "only once" in body and "ignore this email" in body


async def test_only_a_hash_of_the_token_is_stored_and_it_expires(session, outbox):
    await add_admin(session)
    request_reset()

    token = token_from(outbox[0])
    (row,) = (await session.scalars(select(PasswordResetToken))).all()
    assert row.token_hash == hash_reset_token(token) and token not in row.token_hash
    left = row.expires_at.replace(tzinfo=UTC) - datetime.now(UTC)
    assert timedelta(minutes=29) < left <= timedelta(minutes=30)
    assert row.used_at is None


async def test_the_answer_is_identical_for_everyone(session, outbox):
    await add_admin(session)
    await add_admin(session, email="gone@example.com", active=False)

    known = request_reset()
    unknown = request_reset("nobody@example.com")
    deactivated = request_reset("gone@example.com")

    assert {known.status_code, unknown.status_code, deactivated.status_code} == {202}
    assert known.json() == unknown.json() == deactivated.json()  # so it cannot reveal who the admins are
    assert [m["To"] for m in outbox] == ["ada@example.com"]  # but only the real, active one gets mail


async def test_nothing_is_stored_for_unknown_or_deactivated_accounts(session, outbox):
    await add_admin(session, email="gone@example.com", active=False)
    request_reset("nobody@example.com")
    request_reset("gone@example.com")
    assert (await session.scalars(select(PasswordResetToken))).all() == []


async def test_the_email_address_is_matched_whatever_the_capitalisation(session, outbox):
    await add_admin(session)
    request_reset("ADA@Example.com")
    assert [m["To"] for m in outbox] == ["ada@example.com"]


async def test_asking_again_cancels_the_earlier_link(session, outbox):
    await add_admin(session)
    request_reset()
    request_reset()
    first, second = (token_from(m) for m in outbox)

    assert confirm(first).status_code == 400
    assert confirm(second).status_code == 200
    assert len((await session.scalars(select(PasswordResetToken))).all()) == 1


async def test_expired_tokens_are_cleared_out(session, outbox):
    other = await add_admin(session, email="other@example.com")
    await add_token(session, other, minutes=-5)
    await add_admin(session)
    request_reset()
    rows = (await session.scalars(select(PasswordResetToken))).all()
    assert len(rows) == 1 and rows[0].admin_id != other.id


def test_a_malformed_email_is_rejected(session):
    assert request_reset("not-an-email").status_code == 422
    assert client.post(REQUEST, json={}).status_code == 422
    assert client.post(REQUEST, json={"email": "a@example.com", "extra": 1}).status_code == 422


async def test_the_response_never_contains_the_token(session, outbox):
    await add_admin(session)
    r = request_reset()
    assert token_from(outbox[0]) not in r.text


# --- when mail cannot be sent ----------------------------------------------


async def test_a_mail_failure_gives_the_same_answer_and_logs_no_secrets(session, outbox, monkeypatch, caplog):
    await add_admin(session)

    def boom(msg):
        raise OSError("connection refused for ada@example.com")

    monkeypatch.setattr(mail, "_send", boom)
    with caplog.at_level(logging.ERROR):
        r = request_reset()

    assert r.status_code == 202 and r.json()["message"].startswith("If that address")
    assert "OSError" in caplog.text
    assert "ada@example.com" not in caplog.text


async def test_without_mail_settings_the_request_still_answers_and_logs_a_warning(session, monkeypatch, caplog):
    monkeypatch.setattr(settings, "smtp_host", "")
    await add_admin(session)
    with caplog.at_level(logging.WARNING):
        r = request_reset()
    assert r.status_code == 202 and "email is not configured" in caplog.text
    assert "ada@example.com" not in caplog.text


def test_a_hostile_address_cannot_inject_mail_headers(monkeypatch):
    monkeypatch.setattr(settings, "mail_from", "website@goody.test")
    with pytest.raises(ValueError):
        mail.build_password_reset_message("a@example.com\nBcc: victim@example.com", "tok")


# --- choosing a new password ------------------------------------------------


async def test_a_valid_link_sets_the_new_password(session, outbox):
    await add_admin(session)
    request_reset()

    r = confirm(token_from(outbox[0]))

    assert r.status_code == 200 and "updated" in r.json()["message"]
    assert login(NEW_PASSWORD).status_code == 200
    assert login(OLD_PASSWORD).status_code == 401


async def test_the_new_password_is_stored_only_as_an_argon2_hash(session, outbox):
    admin = await add_admin(session)
    request_reset()
    confirm(token_from(outbox[0]))

    await session.refresh(admin)
    assert admin.password_hash.startswith("$argon2id$") and NEW_PASSWORD not in admin.password_hash
    assert verify_password(NEW_PASSWORD, admin.password_hash)


async def test_a_link_works_only_once(session, outbox):
    await add_admin(session)
    request_reset()
    token = token_from(outbox[0])

    assert confirm(token).status_code == 200
    again = confirm(token, password="yet-another-password")
    assert again.status_code == 400
    assert login(NEW_PASSWORD).status_code == 200  # the second attempt changed nothing


async def test_recovering_the_account_lifts_a_lockout(session, outbox):
    admin = await add_admin(session, failed_login_attempts=3, locked_until=datetime.now(UTC) + timedelta(minutes=10))
    assert login(OLD_PASSWORD).status_code == 401  # locked
    request_reset()
    confirm(token_from(outbox[0]))

    await session.refresh(admin)
    assert admin.failed_login_attempts == 0 and admin.locked_until is None
    assert login(NEW_PASSWORD).status_code == 200


async def test_other_pending_links_are_discarded(session, outbox):
    admin = await add_admin(session)
    request_reset()
    stray = await add_token(session, admin)  # another live link for the same account
    confirm(token_from(outbox[0]))
    assert confirm(stray).status_code == 400


@pytest.mark.parametrize("kind", ["unknown", "expired", "used", "deactivated"])
async def test_bad_links_all_get_the_same_refusal(session, kind):
    admin = await add_admin(session, active=kind != "deactivated")
    token = {
        "unknown": "x" * 43,
        "expired": await add_token(session, admin, minutes=-1),
        "used": await add_token(session, admin, used=True),
        "deactivated": await add_token(session, admin),
    }[kind]

    r = confirm(token)

    assert r.status_code == 400
    assert r.json() == {"detail": "This reset link is invalid or has expired. Please ask for a new one."}
    await session.refresh(admin)
    assert verify_password(OLD_PASSWORD, admin.password_hash)  # nothing changed


@pytest.mark.parametrize("bad", ["", "short", "x" * 11, "x" * 129])
async def test_a_weak_or_oversized_password_is_rejected_without_burning_the_link(session, outbox, bad):
    await add_admin(session)
    request_reset()
    token = token_from(outbox[0])

    assert confirm(token, password=bad).status_code == 422

    assert confirm(token).status_code == 200  # the link still works for a proper password


@pytest.mark.parametrize(
    "body", [{}, {"token": "abc"}, {"new_password": NEW_PASSWORD}, {"token": "", "new_password": NEW_PASSWORD}]
)
def test_missing_fields_are_rejected(session, body):
    assert client.post(CONFIRM, json=body).status_code == 422


async def test_the_exact_length_limits_are_accepted(session, outbox):
    await add_admin(session)
    for password in ("x" * 12, "y" * 128):
        request_reset()
        assert confirm(token_from(outbox[-1]), password=password).status_code == 200


# --- ending old sessions ----------------------------------------------------


async def test_a_reset_ends_sessions_started_before_it(session, outbox):
    admin = await add_admin(session)
    now = datetime.now(UTC)
    stolen = jwt.encode(
        {"sub": str(admin.id), "iat": now - timedelta(minutes=5), "exp": now + timedelta(minutes=55)},
        SECRET,
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {stolen}"}
    assert client.get("/admin/me", headers=headers).status_code == 200  # works before the reset

    request_reset()
    confirm(token_from(outbox[0]))

    assert client.get("/admin/me", headers=headers).status_code == 401  # and not after it


async def test_signing_in_after_a_reset_gives_a_working_session(session, outbox):
    await add_admin(session)
    request_reset()
    confirm(token_from(outbox[0]))

    token = login(NEW_PASSWORD).json()["access_token"]
    assert client.get("/admin/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


async def test_accounts_that_never_reset_are_unaffected(session):
    admin = await add_admin(session)
    token = create_access_token(admin.id)
    assert client.get("/admin/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


# --- abuse limits -----------------------------------------------------------


async def test_too_many_attempts_are_blocked_with_retry_after(session, outbox):
    for _ in range(10):
        assert request_reset("nobody@example.com").status_code == 202
    r = request_reset("nobody@example.com")
    assert r.status_code == 429 and 1 <= int(r.headers["retry-after"]) <= 900


async def test_requests_and_confirmations_share_one_allowance(session):
    for _ in range(5):
        request_reset("nobody@example.com")
        confirm("x" * 43)
    assert confirm("x" * 43).status_code == 429


async def test_the_reset_limit_is_separate_from_the_enquiry_limit(session):
    for _ in range(10):
        request_reset("nobody@example.com")
    form = {"name": "Ada Obi", "email": "ada@example.com", "subject": "Hi", "message": "Hello"}
    assert client.post("/enquiries/contact", json=form).status_code == 201


async def test_the_reset_limit_ignores_a_forged_forwarded_header(session):
    for i in range(10):
        client.post(REQUEST, json={"email": "nobody@example.com"}, headers={"X-Forwarded-For": f"1.2.3.{i}"})
    assert request_reset("nobody@example.com").status_code == 429


# --- sign-in input ----------------------------------------------------------


async def test_an_enormous_login_password_is_rejected_before_hashing(session):
    await add_admin(session)
    assert login("x" * 1025).status_code == 422
    assert login("x" * 1024).status_code == 401  # at the limit it is simply a wrong password
