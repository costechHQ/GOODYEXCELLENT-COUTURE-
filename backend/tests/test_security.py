"""Security regression tests (SRS 8.3). Each one fails if a future change quietly weakens the API."""

import importlib
import inspect
import pkgutil
import re

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, SecretStr

from app import schemas as schemas_package
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_session
from app.main import app, create_app
from app.models import AdminUser
from app.models.enums import AdminRole

client = TestClient(app)
STAFF_ONLY_FORBIDDEN = {("GET", "/admin/enquiries/export.csv")}  # the one Owner-only route
ADMIN_OPEN = {  # admin-prefixed routes that must work without signing in
    ("POST", "/admin/login"),
    ("POST", "/admin/password-reset/request"),
    ("POST", "/admin/password-reset/confirm"),
}
PUBLIC_CHANGING = {  # the ONLY routes outside /admin that may change data
    ("POST", "/enquiries/consultation"),
    ("POST", "/enquiries/order"),
    ("POST", "/enquiries/laundry"),
    ("POST", "/enquiries/contact"),
}
PUBLIC_READING = {
    "/health", "/health/db", "/settings", "/services", "/services/{slug}", "/gallery", "/testimonials", "/media/{name}",
}  # fmt: skip


def operations():
    """Every (METHOD, path) the API offers, from its own OpenAPI schema."""
    paths = app.openapi()["paths"]
    return {(method.upper(), path) for path, item in paths.items() for method in item if method != "parameters"}


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


@pytest.fixture(autouse=True)
def jwt_on(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SecretStr("s" * 40))


@pytest.fixture
async def session(use_database, sqlite_session_factory):
    async with sqlite_session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sqlite_session_factory() as s:
        yield s


@pytest.fixture
async def staff(session):
    admin = AdminUser(email="staff@example.com", password_hash=hash_password("x" * 12), role=AdminRole.staff)
    session.add(admin)
    await session.commit()
    return {"Authorization": f"Bearer {create_access_token(admin.id)}"}


# --- who may call what ------------------------------------------------------


def test_the_route_inventory_is_what_we_expect():
    ops = operations()
    assert len(ops) >= 31  # 16 guarded admin + 3 open admin + 12 public; a lower count means routes went missing
    assert any(p.startswith("/admin") for _, p in ops) and ("POST", "/enquiries/order") in ops


async def test_every_admin_route_refuses_anonymous_and_forged_callers(session):
    protected = [(m, p) for m, p in operations() if p.startswith("/admin") and (m, p) not in ADMIN_OPEN]
    assert len(protected) >= 16  # a lower count would make this test pass while checking nothing
    for method, path in sorted(protected):
        for headers in ({}, {"Authorization": "Bearer junk"}, {"Authorization": "Basic YTpi"}):
            r = client.request(method, concrete(path), json={}, headers=headers)
            assert r.status_code == 401, f"{method} {path} answered {r.status_code} to {headers or 'no credentials'}"


async def test_only_the_owner_only_routes_refuse_staff(session, staff):
    refused = set()
    for method, path in sorted(operations()):
        if path.startswith("/admin") and (method, path) not in ADMIN_OPEN:
            status = client.request(method, concrete(path), json={}, headers=staff).status_code
            assert status != 401, f"{method} {path} rejected a valid Staff token"
            if status == 403:
                refused.add((method, path))
    assert refused == STAFF_ONLY_FORBIDDEN


def test_public_routes_that_change_data_are_exactly_the_four_enquiry_forms():
    changing = {(m, p) for m, p in operations() if m in {"POST", "PUT", "PATCH", "DELETE"} and not p.startswith("/admin")}
    assert changing == PUBLIC_CHANGING


def test_public_read_routes_are_exactly_the_expected_ones():
    reading = {p for m, p in operations() if m == "GET" and not p.startswith("/admin")}
    assert reading == PUBLIC_READING


def test_unknown_admin_paths_do_not_reveal_anything(session):
    r = client.get("/admin/does-not-exist")
    assert r.status_code == 404 and r.json() == {"detail": "Not Found"}


# --- every input model refuses fields it does not know ----------------------


def request_models():
    found = []
    for module in pkgutil.iter_modules(schemas_package.__path__):
        mod = importlib.import_module(f"app.schemas.{module.name}")
        for name, cls in inspect.getmembers(mod, inspect.isclass):
            if issubclass(cls, BaseModel) and cls.__module__ == mod.__name__ and name.endswith(("In", "Create", "Update")):
                found.append(cls)
    return found


def test_there_are_input_models_to_check():
    assert len(request_models()) >= 14


@pytest.mark.parametrize("model", request_models(), ids=lambda m: m.__name__)
def test_input_models_reject_unknown_fields(model):
    """Without this a client could set fields we never meant to expose (status, role, id, ...)."""
    assert model.model_config.get("extra") == "forbid"


# --- documentation and schema -----------------------------------------------


def test_the_interactive_docs_are_available_while_developing():
    dev = TestClient(create_app("development"))
    assert dev.get("/docs").status_code == 200 and dev.get("/openapi.json").status_code == 200


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
def test_in_production_the_docs_and_schema_are_off(path):
    prod = TestClient(create_app("production"))
    assert prod.get(path).status_code == 404
    assert prod.get("/health").status_code == 200  # but the API itself works


# --- response headers -------------------------------------------------------


@pytest.mark.parametrize("path", ["/health", "/settings", "/does-not-exist", "/admin/me", "/media/" + "a" * 32 + "-800.webp"])
def test_every_response_carries_the_safety_headers(session, path):
    r = client.get(path)
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_error_and_refusal_responses_carry_them_too(session):
    refused_size = client.post("/enquiries/contact", content=b"x" * 1_100_000, headers={"Content-Type": "application/json"})
    preflight = client.options(
        "/enquiries/contact",
        headers={"Origin": settings.cors_origins[0], "Access-Control-Request-Method": "POST"},
    )
    for r in (refused_size, preflight, client.get("/admin/me")):
        assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"


def test_the_development_docs_page_is_not_broken_by_the_policy():
    dev = TestClient(create_app("development"))
    assert "content-security-policy" not in dev.get("/docs").headers  # it needs scripts from a CDN
    assert dev.get("/docs").headers["x-content-type-options"] == "nosniff"


async def test_admin_answers_are_never_cached(session, staff):
    for path in ("/admin/me", "/admin/enquiries", "/admin/services", "/admin/testimonials"):
        assert client.get(path, headers=staff).headers["cache-control"] == "no-store", path
    assert client.get("/admin/me").headers["cache-control"] == "no-store"  # even the refusal


def test_public_pages_are_not_marked_no_store(session):
    assert "no-store" not in client.get("/settings").headers.get("cache-control", "")


def test_hsts_is_sent_in_production_only():
    assert "strict-transport-security" not in TestClient(create_app("development")).get("/health").headers
    hsts = TestClient(create_app("production")).get("/health").headers["strict-transport-security"]
    assert hsts == "max-age=31536000"


# --- no detail leaks --------------------------------------------------------


def test_an_unexpected_failure_shows_the_visitor_nothing(session):
    async def explode():
        raise RuntimeError("postgres://goody:hunter2@db/goody refused the connection")

    app.dependency_overrides[get_session] = explode
    try:
        r = TestClient(app, raise_server_exceptions=False).get("/settings")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 500
    assert "hunter2" not in r.text and "postgres" not in r.text and "Traceback" not in r.text


def test_settings_never_print_their_secrets():
    shown = repr(settings) + str(settings.model_dump())
    for secret in (settings.jwt_secret, settings.smtp_password, settings.owner_password):
        assert isinstance(secret, SecretStr)
    assert "s" * 40 not in shown


# --- sign-in abuse limit ----------------------------------------------------


def login(email="nobody@example.com", **kw):
    return client.post("/admin/login", json={"email": email, "password": "not-the-password"}, **kw)


async def test_one_address_cannot_make_endless_sign_in_attempts(session):
    for _ in range(20):
        assert login().status_code == 401  # wrong, but allowed to try
    blocked = login()
    assert blocked.status_code == 429 and 1 <= int(blocked.headers["retry-after"]) <= 600


async def test_the_limit_counts_attempts_at_different_accounts_together(session):
    for n in range(20):
        login(email=f"person{n}@example.com")  # spraying many accounts from one address
    assert login(email="another@example.com").status_code == 429


async def test_a_forged_forwarded_header_cannot_reset_the_sign_in_limit(session):
    for n in range(20):
        login(headers={"X-Forwarded-For": f"10.0.0.{n}"})
    assert login(headers={"X-Forwarded-For": "8.8.8.8"}).status_code == 429


async def test_the_sign_in_limit_does_not_block_other_routes(session):
    for _ in range(21):
        login()
    assert client.get("/settings").status_code in (200, 404)
    assert client.post("/enquiries/contact", json={"name": "Ada", "email": "a@example.com", "subject": "Hi", "message": "x"}).status_code == 201


# --- request size -----------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [("POST", "/enquiries/contact"), ("POST", "/enquiries/consultation"), ("POST", "/admin/login"), ("PATCH", "/admin/gallery/1")],
)
def test_ordinary_requests_have_a_one_megabyte_limit(session, method, path):
    r = client.request(method, path, content=b"x" * 1_100_000, headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json() == {"detail": "That upload is too large."}


def test_normal_sized_requests_are_unaffected(session):
    body = {"name": "Ada Obi", "email": "ada@example.com", "subject": "Hello", "message": "x" * 1900}
    assert client.post("/enquiries/contact", json=body).status_code == 201


def test_reading_is_never_limited(session):
    assert client.get("/services", headers={"X-Padding": "x" * 5000}).status_code == 200
