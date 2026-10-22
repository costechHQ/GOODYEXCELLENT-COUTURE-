from pydantic import BaseModel, ConfigDict

from app.models.enums import GalleryCategory


class GalleryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    thumb_url: str | None
    caption: str | None
    alt_text: str
    category: GalleryCategory
    featured: bool
    service_id: int | None
