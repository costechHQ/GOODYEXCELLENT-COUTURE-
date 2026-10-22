from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import GalleryCategory


class GalleryItem(TimestampMixin, Base):
    __tablename__ = "gallery_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_url: Mapped[str] = mapped_column(String(500))
    thumb_url: Mapped[str | None] = mapped_column(String(500))  # FR-29, NFR-04
    caption: Mapped[str | None] = mapped_column(String(300))
    alt_text: Mapped[str] = mapped_column(String(300), default="")  # CR-04, NFR-17
    category: Mapped[GalleryCategory] = mapped_column(Enum(GalleryCategory), index=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    service_id: Mapped[int | None] = mapped_column(
        ForeignKey("services.id", ondelete="SET NULL")
    )  # FR-22
