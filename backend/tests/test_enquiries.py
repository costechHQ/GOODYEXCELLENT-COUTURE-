import pytest
from sqlalchemy import func, select

from app.core.limiter import limiter
from app.db.seed import seed
from app.models import Enquiry
from app.schemas.enquiry import normalise_phone

URL = "/api/v1/enquiries"
CONSULT = {"name": "Chidi Okafor", "phone": "08060036531", "preferred_contact": "whatsapp"}


async def count(session) -> int:
    return await session.scalar(select(func.count()).select_from(Enquiry))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("08060036531", "+2348060036531"),
        ("0806 003 6531", "+2348060036531"),
        ("+2348060036531", "+2348060036531"),
        ("2349024662143", "+2349024662143"),
        ("+44 20 7946 0958", "+442079460958"),
    ],
)
def test_phone_normalisation(raw, expected):
    assert normalise_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "123", "0806003", "abcdefghijk", "+0123456789"])
def test_phone_rejected(raw):
    with pytest.raises(ValueError):
        normalise_phone(raw)


async def test_consultation_saved_and_email_queued(client, session, sent):
    await seed(session)
    r = await client.post(f"{URL}/consultation", json={**CONSULT, "service_id": 1, "message": "Hi"})
    assert r.status_code == 201
    body = r.json()
    assert "respond" in body["message"] and "hour" not in body["message"]  # FR-34
    row = await session.get(Enquiry, body["id"])
    assert (row.type.value, row.status.value, row.phone) == (
        "consultation",
        "new",
        "+2348060036531",
    )
    assert sent == [body["id"]]


async def test_order_enquiry_fields(client, session, sent):
    payload = {
        **CONSULT,
        "garment_type": "Senator",
        "occasion": "Wedding",
        "needed_by": "2026-12-20",
        "quantity": 3,
        "fabric_preference": "Navy",
    }
    r = await client.post(f"{URL}/order", json=payload)
    assert r.status_code == 201
    row = await session.get(Enquiry, r.json()["id"])
    assert (row.garment_type, row.quantity, str(row.needed_by)) == ("Senator", 3, "2026-12-20")


async def test_laundry_and_contact(client, session, sent):
    r = await client.post(
        f"{URL}/laundry", json={"name": "Ada", "phone": "08060036531", "garment_types": "Suits"}
    )
    assert r.status_code == 201
    r = await client.post(
        f"{URL}/contact",
        json={"name": "Ada", "email": "ada@example.com", "subject": "Hello", "message": "Hi there"},
    )
    assert r.status_code == 201
    assert len(sent) == 2


async def test_contact_needs_phone_or_email(client, session, sent):
    r = await client.post(f"{URL}/contact", json={"name": "Ada", "subject": "s", "message": "m"})
    assert r.status_code == 422
    assert await count(session) == 0


async def test_validation_errors_store_nothing(client, session, sent):
    for payload in (
        {**CONSULT, "phone": "12345"},
        {**CONSULT, "name": "A"},
        {**CONSULT, "email": "not-an-email"},
        {**CONSULT, "preferred_contact": "pigeon"},
        {**CONSULT, "service_id": 999},
        {**CONSULT, "unexpected": 1},
    ):
        assert (await client.post(f"{URL}/consultation", json=payload)).status_code == 422
    assert await count(session) == 0 and sent == []


async def test_honeypot_looks_successful_but_stores_nothing(client, session, sent):
    r = await client.post(f"{URL}/consultation", json={**CONSULT, "website": "http://spam"})
    assert r.status_code == 201
    assert await count(session) == 0 and sent == []


async def test_rate_limit(client, sent):
    limiter.enabled = True
    limiter.reset()
    codes = [(await client.post(f"{URL}/consultation", json=CONSULT)).status_code for _ in range(7)]
    assert codes[:5] == [201] * 5 and codes[5] == 429


async def test_email_failure_never_loses_the_enquiry(client, session, session_factory, monkeypatch):
    from app.services import email

    async def boom(msg):
        raise ConnectionRefusedError

    monkeypatch.setattr(email, "SessionLocal", session_factory)
    monkeypatch.setattr(email, "send_message", boom)
    r = await client.post(f"{URL}/consultation", json=CONSULT)
    assert r.status_code == 201  # NFR-15
    row = await session.get(Enquiry, r.json()["id"])
    assert row is not None and row.email_sent_at is None


async def test_email_success_is_recorded(client, session, session_factory, monkeypatch):
    from app.services import email

    delivered = []

    async def ok(msg):
        delivered.append(msg)

    monkeypatch.setattr(email, "SessionLocal", session_factory)
    monkeypatch.setattr(email, "send_message", ok)
    r = await client.post(f"{URL}/consultation", json={**CONSULT, "message": "<script>x</script>"})
    row = await session.get(Enquiry, r.json()["id"])
    assert row.email_sent_at is not None
    msg = delivered[0]
    assert msg["To"] == "goodnessngwuta@gmail.com"
    assert msg.get_content_type() == "text/plain"  # visitor input is never sent as HTML
