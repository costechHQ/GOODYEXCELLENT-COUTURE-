from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.common import ImageUrl


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    description: str
    image_url: str | None


# --- admin (FR-21, FR-52) ---------------------------------------------------

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class ServiceUpdate(BaseModel):
    """Send only the fields to change. The slug is not editable: it forms the public URL.
    Only `image_url` may be set to null (to remove the picture)."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: Description | None = None
    image_url: ImageUrl | None = None
    display_order: int | None = Field(default=None, ge=0)
    visible: bool | None = None

    @model_validator(mode="after")
    def no_nulls_except_image(self):
        for name in self.model_fields_set - {"image_url"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class ServiceAdminOut(ServiceOut):
    display_order: int
    visible: bool
