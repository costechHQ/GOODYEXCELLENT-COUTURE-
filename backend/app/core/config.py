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


settings = Settings()
