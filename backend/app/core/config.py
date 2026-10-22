from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (NFR-12)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GOODYEXCELLENT COUTURE API"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://goody:goody@localhost:5432/goody"

    # TS-01: only the site's own domain may call the API.
    cors_origins: list[str] = ["http://localhost:3000"]

    # Admin auth (FR-51, NFR-06)
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    max_failed_logins: int = 5
    lockout_minutes: int = 15

    # Email (IF-02, FR-35, FR-58)
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = False
    mail_from: EmailStr = "no-reply@example.com"
    enquiry_email: EmailStr = "goodnessngwuta@gmail.com"

    # First Owner account created by the seed script (FR-51)
    admin_email: EmailStr | None = None
    admin_password: str | None = None
    admin_name: str = "Owner"

    # Uploads (FR-31, NFR-08, TS-05)
    max_upload_bytes: int = 5 * 1024 * 1024
    max_reference_images: int = 5
    upload_dir: str = "uploads"  # local dev; swap for object storage in production

    # Rate limiting (FR-37)
    enquiry_rate_limit: str = "5/minute"


settings = Settings()
