from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.schemas.common import ImageUrl


class TestimonialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_name: str
    quote: str
    photo_url: str | None


# --- admin (FR-50) ----------------------------------------------------------

ClientName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Quote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class TestimonialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_name: ClientName
    quote: Quote
    photo_url: ImageUrl | None = None
    # Hidden until the owner approves it, so nothing is published without consent (FR-49, CR-03).
    visible: bool = False


class TestimonialUpdate(BaseModel):
    """Send only the fields to change. Only `photo_url` may be set to null (to remove the photo)."""

    model_config = ConfigDict(extra="forbid")

    client_name: ClientName | None = None
    quote: Quote | None = None
    photo_url: ImageUrl | None = None
    visible: bool | None = None

    @model_validator(mode="after")
    def no_nulls_except_photo(self):
        for name in self.model_fields_set - {"photo_url"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class TestimonialAdminOut(TestimonialOut):
    visible: bool
    created_at: datetime
