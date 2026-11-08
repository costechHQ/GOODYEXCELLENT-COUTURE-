from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration comes from environment variables or a local .env file (NFR-12)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GOODYEXCELLENT COUTURE API"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://goody:goody@localhost:5432/goody"

    # Origins allowed to call the API from a browser (TS-01). In production, set this to the
    # site's own domain only, as JSON: CORS_ORIGINS=["https://yourdomain.com"]
    cors_origins: list[str] = ["http://localhost:3000"]

    # Rate limit on the public enquiry forms (FR-37): at most this many attempts per client IP
    # in the window, counted across all four forms together.
    rate_limit_max_requests: int = 10
    rate_limit_window_seconds: int = 600

    # Enquiry notification email (FR-35, IF-02). Nothing is sent until SMTP_HOST and
    # ENQUIRY_NOTIFY_TO are both set.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"  # 587 = starttls, 465 = ssl
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    mail_from: str = ""  # defaults to the notify address; many providers require their own domain
    enquiry_notify_to: str = ""  # the brand's enquiry inbox

    # First Owner account, created by `python -m app.db.seed` only when no Owner exists yet.
    # Set both, run the seed once, then remove OWNER_PASSWORD from the environment.
    owner_email: str = ""
    owner_password: SecretStr = SecretStr("")

    # Admin sign-in tokens (FR-51). There is deliberately no default secret: until JWT_SECRET is
    # set to at least 32 random characters, sign-in is unavailable. Generate one with:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    jwt_secret: SecretStr = SecretStr("")
    access_token_minutes: int = 60


settings = Settings()
