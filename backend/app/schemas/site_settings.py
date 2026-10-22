from pydantic import BaseModel, ConfigDict


class SiteSettingsOut(BaseModel):
    """What the frontend receives. Only fields listed here ever leave the API."""

    model_config = ConfigDict(from_attributes=True)  # allow building from a SQLAlchemy row

    phone_numbers: list[str]
    whatsapp_link: str
    email: str
    address: str | None
    map_link: str | None
    opening_hours: dict | None
    social_links: dict | None
