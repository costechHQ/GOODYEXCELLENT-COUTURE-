import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.rate_limit import RateLimiter, enquiry_limiter
from app.db.base import Base
from app.main import app

client = TestClient(app)


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


# --- the limiter on its own -------------------------------------------------


def test_allows_up_to_the_limit_then_blocks():
    limiter = RateLimiter(3, 60, FakeClock())
    assert [limiter.hit("a") for _ in range(3)] == [None, None, None]
    assert limiter.hit("a") == 60


def test_each_client_has_its_own_count():
    limiter = RateLimiter(1, 60, FakeClock())
    assert limiter.hit("a") is None
    assert limiter.hit("b") is None
    assert limiter.hit("a") is not None


def test_window_slides_and_retry_after_counts_down():
    clock = FakeClock()
    limiter = RateLimiter(2, 60, clock)
    limiter.hit("a")  # t=0
    clock.now += 30
    limiter.hit("a")  # t=30
    clock.now += 10
    assert limiter.hit("a") == 20  # the t=0 hit leaves the window at t=60
    clock.now += 20
    assert limiter.hit("a") is None  # t=60: one slot is free again


def test_blocked_attempts_are_not_counted():
    clock = FakeClock()
    limiter = RateLimiter(1, 60, clock)
    limiter.hit("a")
    clock.now += 59
    limiter.hit("a")  # blocked; must not extend the block
    clock.now += 1
    assert limiter.hit("a") is None


def test_idle_clients_are_swept_when_many_are_tracked(monkeypatch):
    monkeypatch.setattr("app.core.rate_limit._SWEEP_ABOVE", 2)
    clock = FakeClock()
    limiter = RateLimiter(1, 60, clock)
    for k in "abc":
        limiter.hit(k)
    clock.now += 61
    limiter.hit("d")
    assert set(limiter._hits) == {"d"}


def test_settings_defaults_and_overrides(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_MAX_REQUESTS", raising=False)
    monkeypatch.delenv("RATE_LIMIT_WINDOW_SECONDS", raising=False)
    s = Settings(_env_file=None)
    assert (s.rate_limit_max_requests, s.rate_limit_window_seconds) == (10, 600)
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "3")
    assert Settings(_env_file=None).rate_limit_max_requests == 3


# --- on the endpoints -------------------------------------------------------

FORMS = {
    "consultation": {"name": "Ada Obi", "phone": "08012345678", "preferred_contact": "call"},
    "order": {"name": "Ada Obi", "phone": "08012345678", "preferred_contact": "call", "garment_type": "Suit"},
    "laundry": {"name": "Ada Obi", "phone": "08012345678", "garment_type": "Suit"},
    "contact": {"name": "Ada Obi", "phone": "08012345678", "subject": "Hello", "message": "Hi"},
}


@pytest.fixture
async def small_limit(use_database, sqlite_session_factory, monkeypatch):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(enquiry_limiter, "max_requests", 3)


def test_over_the_limit_returns_429_with_retry_after(small_limit):
    for _ in range(3):
        assert client.post("/enquiries/contact", json=FORMS["contact"]).status_code == 201
    r = client.post("/enquiries/contact", json=FORMS["contact"])
    assert r.status_code == 429
    assert 1 <= int(r.headers["retry-after"]) <= 600
    assert "wait" in r.json()["detail"]


def test_the_count_is_shared_across_all_four_forms(small_limit):
    for form in ("consultation", "order", "laundry"):
        assert client.post(f"/enquiries/{form}", json=FORMS[form]).status_code == 201
    assert client.post("/enquiries/contact", json=FORMS["contact"]).status_code == 429


def test_invalid_and_honeypot_attempts_count_too(small_limit):
    client.post("/enquiries/contact", json={})  # invalid
    client.post("/enquiries/contact", json=FORMS["contact"] | {"website": "spam"})  # honeypot
    client.post("/enquiries/contact", json={})
    assert client.post("/enquiries/contact", json=FORMS["contact"]).status_code == 429


def test_a_forged_forwarded_header_cannot_dodge_the_limit(small_limit):
    for i in range(3):
        client.post("/enquiries/contact", json=FORMS["contact"], headers={"X-Forwarded-For": f"1.2.3.{i}"})
    r = client.post("/enquiries/contact", json=FORMS["contact"], headers={"X-Forwarded-For": "9.9.9.9"})
    assert r.status_code == 429


def test_other_endpoints_are_not_limited(small_limit):
    for _ in range(10):
        assert client.get("/health").status_code == 200
