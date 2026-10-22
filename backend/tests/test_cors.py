from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app

client = TestClient(app)


def preflight(origin: str):
    """The browser sends this OPTIONS request first to ask 'may I call you from here?'"""
    return client.options(
        "/settings",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_allowed_origin_is_accepted():
    response = preflight("http://localhost:3000")
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_other_origin_is_rejected():
    response = preflight("https://evil.example.com")
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_origins_can_be_set_from_environment(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://goodyexcellentcouture.com"]')
    assert Settings(_env_file=None).cors_origins == ["https://goodyexcellentcouture.com"]
