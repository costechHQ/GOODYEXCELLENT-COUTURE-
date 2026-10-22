from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration comes from environment variables or a local .env file (NFR-12)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GOODYEXCELLENT COUTURE API"
    environment: str = "development"


settings = Settings()
