import logging
import smtplib
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

from app.core import mail
from app.core.config import Settings, settings
from app.db.base import Base
from app.main import app
from app.models import Enquiry

client = TestClient(app)


def _post_form(form, payload):
    """The order form is multipart (it can carry pictures); the other three forms are JSON."""
    body = {"data": payload} if form == "order" else {"json": payload}
    return client.post(f"/enquiries/{form}", **body)


class FakeSMTP:
    """Stands in for smtplib.SMTP / SMTP_SSL and records what happens."""

    instances: ClassVar[list["FakeSMTP"]] = []
    fail_on_send = False

    def __init__(self, host, port, **kwargs):
        self.host, self.port, self.kwargs = host, port, kwargs
        self.started_tls = False
        self.login_args = None
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, **kwargs):
        self.started_tls = True

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, msg):
        if FakeSMTP.fail_on_send:
            raise smtplib.SMTPException("boom with secret@example.com")
        self.sent.append(msg)


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch):
    FakeSMTP.instances = []
    FakeSMTP.fail_on_send = False
    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", FakeSMTP)


@pytest.fixture
def mail_on(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "enquiry_notify_to", "orders@goody.test")
    monkeypatch.setattr(settings, "mail_from", "website@goody.test")


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


CONSULT = {"name": "Ada Obi", "phone": "0801 234 5678", "preferred_contact": "call", "email": "ada@example.com"}


# --- settings ---------------------------------------------------------------


def test_mail_settings_default_to_off(monkeypatch):
    for var in ("SMTP_HOST", "SMTP_PORT", "SMTP_SECURITY", "ENQUIRY_NOTIFY_TO"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert (s.smtp_host, s.smtp_port, s.smtp_security, s.enquiry_notify_to) == ("", 587, "starttls", "")


def test_password_is_not_shown_in_repr():
    assert "hunter2" not in repr(Settings(_env_file=None, smtp_password="hunter2"))


# --- the message ------------------------------------------------------------


def test_message_lists_the_filled_fields_and_replies_to_the_client(mail_on):
    msg = mail.build_enquiry_message(7, "order", {"name": "Tunde", "email": "t@example.com", "quantity": 3, "occasion": None})

    assert msg["To"] == "orders@goody.test"
    assert msg["From"] == "website@goody.test"
    assert msg["Reply-To"] == "t@example.com"
    assert msg["Subject"] == "[New order enquiry] Tunde"
    body = msg.get_content()
    assert "#7" in body and "Quantity: 3" in body and "Name: Tunde" in body
    assert "Occasion" not in body  # empty fields are left out


def test_no_reply_to_when_the_client_gave_no_email(mail_on):
    assert mail.build_enquiry_message(1, "laundry", {"name": "Emeka"})["Reply-To"] is None


def test_header_injection_through_the_name_is_flattened(mail_on):
    msg = mail.build_enquiry_message(1, "general", {"name": "Eve\r\nBcc: victim@example.com"})
    assert "\n" not in msg["Subject"] and "\r" not in msg["Subject"]
    assert msg["Bcc"] is None


# --- sending ----------------------------------------------------------------


def test_nothing_is_sent_when_mail_is_not_configured():
    mail.notify_new_enquiry(1, "general", {"name": "A"})
    assert FakeSMTP.instances == []


def test_needs_both_a_server_and_a_recipient(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    mail.notify_new_enquiry(1, "general", {"name": "A"})
    assert FakeSMTP.instances == []


def test_starttls_and_login(mail_on, monkeypatch):
    monkeypatch.setattr(settings, "smtp_username", "user")
    monkeypatch.setattr(settings, "smtp_password", SecretStr("pw"))
    mail.notify_new_enquiry(1, "general", {"name": "Ada"})
    smtp = FakeSMTP.instances[0]
    assert (smtp.host, smtp.port, smtp.started_tls, smtp.login_args) == ("smtp.test", 587, True, ("user", "pw"))
    assert smtp.kwargs["timeout"] == 10 and len(smtp.sent) == 1


def test_ssl_mode_does_not_also_starttls(mail_on, monkeypatch):
    monkeypatch.setattr(settings, "smtp_security", "ssl")
    mail.notify_new_enquiry(1, "general", {"name": "Ada"})
    assert FakeSMTP.instances[0].started_tls is False and FakeSMTP.instances[0].login_args is None


def test_a_mail_failure_is_logged_without_personal_details(mail_on, caplog):
    FakeSMTP.fail_on_send = True
    with caplog.at_level(logging.ERROR):
        mail.notify_new_enquiry(9, "general", {"name": "Ada", "email": "secret@example.com"})
    assert "#9" in caplog.text and "SMTPException" in caplog.text
    assert "secret@example.com" not in caplog.text and "Ada" not in caplog.text


# --- through the endpoints --------------------------------------------------


async def test_new_enquiry_is_saved_and_emailed(session, mail_on):
    r = client.post("/enquiries/consultation", json=CONSULT)

    assert r.status_code == 201
    msg = FakeSMTP.instances[0].sent[0]
    assert msg["Subject"] == "[New consultation enquiry] Ada Obi"
    assert f"#{r.json()['id']}" in msg.get_content()
    assert "+2348012345678" in msg.get_content()  # the normalised number
    assert len((await session.scalars(select(Enquiry))).all()) == 1


@pytest.mark.parametrize(
    ("path", "payload", "kind"),
    [
        ("order", CONSULT | {"garment_type": "Agbada"}, "order"),
        ("laundry", {"name": "Emeka", "phone": "08031112222", "garment_type": "Suit"}, "laundry"),
        ("contact", {"name": "Chika", "email": "c@example.com", "subject": "Hi", "message": "Hello"}, "general"),
    ],
)
def test_every_form_sends_an_email(session, mail_on, path, payload, kind):
    assert _post_form(path, payload).status_code == 201
    assert f"[New {kind} enquiry]" in FakeSMTP.instances[0].sent[0]["Subject"]


async def test_a_mail_failure_never_loses_the_enquiry_or_errors_the_visitor(session, mail_on):
    FakeSMTP.fail_on_send = True
    r = client.post("/enquiries/consultation", json=CONSULT)
    assert r.status_code == 201
    assert len((await session.scalars(select(Enquiry))).all()) == 1


def test_honeypot_hits_send_no_email(session, mail_on):
    assert client.post("/enquiries/consultation", json=CONSULT | {"website": "spam"}).status_code == 201
    assert FakeSMTP.instances == []


def test_invalid_submissions_send_no_email(session, mail_on):
    assert client.post("/enquiries/consultation", json=CONSULT | {"phone": "bad"}).status_code == 422
    assert FakeSMTP.instances == []
