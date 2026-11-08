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

    # Failed-login lockout (NFR-06): this many wrong passwords in a row lock the account.
    login_max_failures: int = 5
    login_lock_minutes: int = 15

    # Password reset by email (FR-56). The emailed link points at the website, so FRONTEND_URL must
    # be the site's real address in production (no trailing slash needed).
    frontend_url: str = "http://localhost:3000"
    password_reset_minutes: int = 30

    # Image uploads (FR-29). Files are saved in UPLOAD_DIR and served from API_PUBLIC_URL/media/.
    # In production the folder must be on persistent storage, or uploads vanish on every redeploy.
    upload_dir: str = "uploads"
    api_public_url: str = "http://localhost:8000"
    max_upload_bytes: int = 5 * 1024 * 1024


settings = Settings()
