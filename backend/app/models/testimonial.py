from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Testimonial(TimestampMixin, Base):
    __tablename__ = "testimonials"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_name: Mapped[str] = mapped_column(String(120))
    quote: Mapped[str] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    visible: Mapped[bool] = mapped_column(Boolean, default=False)  # FR-49: owner-approved only
