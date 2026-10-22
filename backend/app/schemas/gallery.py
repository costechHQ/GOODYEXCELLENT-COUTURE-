from pydantic import BaseModel, ConfigDict

from app.models.enums import GalleryCategory


class GalleryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    caption: str | None
    alt_text: str
    category: GalleryCategory
    featured: bool
