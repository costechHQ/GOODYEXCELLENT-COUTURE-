from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import GalleryCategory


class GalleryItem(Base):
    """One photo in the portfolio (FR-24 to FR-29)."""

    __tablename__ = "gallery_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_url: Mapped[str] = mapped_column(String(500))  # URL only; files live elsewhere (TS-05)
    caption: Mapped[str | None] = mapped_column(String(300))
    alt_text: Mapped[str] = mapped_column(String(300), default="")  # every image needs one (CR-04)
    category: Mapped[GalleryCategory] = mapped_column(Enum(GalleryCategory, validate_strings=True), index=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)  # shown on the Home page
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
