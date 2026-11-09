from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SiteSettings(Base):
    """Single-row table (id is always 1), edited in one place and used site-wide (FR-55)."""

    __tablename__ = "site_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    phone_numbers: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["+2348060036531", "+2349024662143"])
    whatsapp_link: Mapped[str] = mapped_column(String(300), default="https://wa.me/2348060036531")
    email: Mapped[str] = mapped_column(String(255), default="goodnessngwuta@gmail.com")
    address: Mapped[str | None] = mapped_column(Text)
    map_link: Mapped[str | None] = mapped_column(String(500))
    # none_as_null: clearing one of these stores a true SQL NULL, the same as a value that was never set.
    # (By default SQLAlchemy would store the JSON text "null", which `IS NULL` queries do not match.)
    opening_hours: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    social_links: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
