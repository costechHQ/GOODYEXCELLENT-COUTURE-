from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.enums import GalleryCategory
from app.schemas.common import ImageUrl


class GalleryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    caption: str | None
    alt_text: str
    category: GalleryCategory
    featured: bool


# --- admin (FR-28) ----------------------------------------------------------

Caption = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
AltText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class GalleryItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_url: ImageUrl
    alt_text: AltText  # every image needs one (CR-04)
    category: GalleryCategory
    caption: Caption | None = None
    featured: bool = False
    display_order: int | None = Field(default=None, ge=0)  # omitted: placed at the end


class GalleryItemUpdate(BaseModel):
    """Send only the fields to change. Only `caption` may be set to null (to clear it)."""

    model_config = ConfigDict(extra="forbid")

    image_url: ImageUrl | None = None
    alt_text: AltText | None = None
    category: GalleryCategory | None = None
    caption: Caption | None = None
    featured: bool | None = None
    display_order: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def no_nulls_except_caption(self):
        for name in self.model_fields_set - {"caption"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class GalleryItemAdminOut(GalleryItemOut):
    display_order: int
    created_at: datetime
