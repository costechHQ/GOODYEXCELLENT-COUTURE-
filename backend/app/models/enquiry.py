from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import ContactMethod, EnquiryStatus, EnquiryType


class Enquiry(TimestampMixin, Base):
    """One table for consultation, order, laundry and general enquiries (SRS 6.1)."""

    __tablename__ = "enquiries"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[EnquiryType] = mapped_column(Enum(EnquiryType), index=True)
    status: Mapped[EnquiryStatus] = mapped_column(
        Enum(EnquiryStatus), default=EnquiryStatus.new, index=True
    )

    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(255))
    preferred_contact: Mapped[ContactMethod | None] = mapped_column(Enum(ContactMethod))

    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id", ondelete="SET NULL"))
    gallery_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("gallery_items.id", ondelete="SET NULL")
    )  # FR-27: "Order something like this"

    subject: Mapped[str | None] = mapped_column(String(200))  # FR-47
    message: Mapped[str | None] = mapped_column(Text)
    preferred_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # FR-30

    # Order-enquiry fields (FR-31)
    garment_type: Mapped[str | None] = mapped_column(String(120))
    occasion: Mapped[str | None] = mapped_column(String(120))
    needed_by: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[int | None]
    fabric_preference: Mapped[str | None] = mapped_column(String(200))
    reference_images: Mapped[list[str]] = mapped_column(JSON, default=list)  # URLs only (TS-05)

    internal_notes: Mapped[str | None] = mapped_column(Text)  # FR-54
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # NFR-15

    service = relationship("Service")
    gallery_item = relationship("GalleryItem")
