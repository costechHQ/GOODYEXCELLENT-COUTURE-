import re
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

from app.core.phone import normalise_phone


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


# --- admin (FR-55) ----------------------------------------------------------

_HTTPS = TypeAdapter(AnyHttpUrl)
_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_PLATFORM = re.compile(r"[a-z][a-z0-9]{1,19}")  # a short lowercase name such as "instagram"


def _https_only(value: str) -> str:
    # These links appear on every page, so only secure addresses are allowed: this also rules out
    # javascript:, data: and relative paths.
    if _HTTPS.validate_python(value).scheme != "https":
        raise ValueError("The link must start with https://")
    return value


HttpsLink = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    AfterValidator(_https_only),
]
HoursText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class SiteSettingsUpdate(BaseModel):
    """Send only the fields to change. `address`, `map_link`, `opening_hours` and `social_links` may be
    null to clear them; the phone numbers, WhatsApp link and email may not, because the site must
    always be reachable. Opening hours and social links replace the whole value, they are not merged."""

    model_config = ConfigDict(extra="forbid")

    phone_numbers: list[str] | None = Field(default=None, min_length=1, max_length=5)
    whatsapp_link: HttpsLink | None = Field(default=None, max_length=300)
    email: EmailStr | None = None
    address: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] | None = None
    map_link: HttpsLink | None = None
    opening_hours: dict[Literal[_DAYS], HoursText] | None = Field(default=None, max_length=7)
    social_links: dict[str, HttpsLink] | None = Field(default=None, max_length=10)

    @field_validator("phone_numbers")
    @classmethod
    def normalise_numbers(cls, numbers: list[str] | None) -> list[str] | None:
        if numbers is None:
            return None
        normalised = [normalise_phone(n) for n in numbers]  # raises a clear error for a bad number
        return list(dict.fromkeys(normalised))  # drop duplicates, keep the order

    @field_validator("social_links")
    @classmethod
    def platform_names(cls, links: dict[str, str] | None) -> dict[str, str] | None:
        if links is None:
            return None
        for name in links:
            if not _PLATFORM.fullmatch(name):
                raise ValueError(
                    f"'{name}' is not a valid network name; use a short lowercase word such as 'instagram'"
                )
        return links

    @model_validator(mode="after")
    def only_optional_fields_may_be_null(self):
        required = {"phone_numbers", "whatsapp_link", "email"}
        for name in self.model_fields_set & required:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self
