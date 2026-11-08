from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.storage import public_url
from app.db.base import Base


class EnquiryImage(Base):
    """A reference picture a client attached to an order enquiry (FR-31).

    The files live in storage under `{image_id}-{width}.webp`; this row records which ones belong
    to which enquiry.
    """

    __tablename__ = "enquiry_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    enquiry_id: Mapped[int] = mapped_column(ForeignKey("enquiries.id", ondelete="CASCADE"), index=True)
    image_id: Mapped[str] = mapped_column(String(32), unique=True)
    width: Mapped[int] = mapped_column(Integer)  # the original, after rotating it upright
    height: Mapped[int] = mapped_column(Integer)
    widths: Mapped[list[int]] = mapped_column(JSON)  # the sizes that were stored, smallest first
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def url(self) -> str:
        """The largest stored size."""
        return public_url(f"{self.image_id}-{max(self.widths)}.webp")

    @property
    def variants(self) -> dict[str, str]:
        return {str(w): public_url(f"{self.image_id}-{w}.webp") for w in sorted(self.widths)}
