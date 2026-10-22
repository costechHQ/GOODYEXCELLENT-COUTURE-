from app.core.config import Settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert Settings(_env_file=None).environment == "development"


def test_environment_variable_overrides_default(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert Settings(_env_file=None).environment == "production"


def test_unknown_variables_are_ignored(monkeypatch):
    monkeypatch.setenv("SOMETHING_ELSE", "x")
    Settings(_env_file=None)  # must not raise
