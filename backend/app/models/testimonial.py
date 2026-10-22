from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Testimonial(Base):
    """A client's quote (FR-12, FR-49, FR-50)."""

    __tablename__ = "testimonials"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_name: Mapped[str] = mapped_column(String(120))
    quote: Mapped[str] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    # Hidden until the owner approves it, so nothing is published without consent (FR-49, CR-03).
    visible: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
