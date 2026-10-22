from pydantic import BaseModel, ConfigDict


class SiteSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    phone_numbers: list[str]
    whatsapp_link: str
    email: str
    address: str | None
    map_link: str | None
    opening_hours: dict | None
    social_links: dict | None
