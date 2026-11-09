from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ContactMethod, EnquiryStatus, EnquiryType

if TYPE_CHECKING:
    from app.models.enquiry_image import EnquiryImage


class Enquiry(Base):
    """A form submission of any type (FR-30 to FR-47, FR-53, FR-54).

    One table for all four forms: shared columns are required, type-specific ones are optional.
    The API layer decides which fields each form must supply.
    """

    __tablename__ = "enquiries"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[EnquiryType] = mapped_column(Enum(EnquiryType, validate_strings=True), index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30))  # optional: the contact form takes phone or email (FR-47)
    email: Mapped[str | None] = mapped_column(String(254))
    preferred_contact: Mapped[ContactMethod | None] = mapped_column(Enum(ContactMethod, validate_strings=True))
    service: Mapped[str | None] = mapped_column(String(120))  # service of interest (FR-30)
    subject: Mapped[str | None] = mapped_column(String(200))  # general contact form (FR-47)
    message: Mapped[str | None] = mapped_column(Text)
    preferred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # consultation date and time
    garment_type: Mapped[str | None] = mapped_column(String(200))  # order and laundry (FR-31, FR-42)
    occasion: Mapped[str | None] = mapped_column(String(200))
    needed_by: Mapped[date | None] = mapped_column(Date)  # event or needed-by date (FR-31)
    quantity: Mapped[int | None] = mapped_column(Integer)
    fabric_preference: Mapped[str | None] = mapped_column(String(200))
    # Staff-only fields (FR-53, FR-54). Never exposed by public endpoints.
    status: Mapped[EnquiryStatus] = mapped_column(
        Enum(EnquiryStatus, validate_strings=True),
        default=EnquiryStatus.new,
        server_default=EnquiryStatus.new.value,
        index=True,
    )
    internal_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Order enquiries only (FR-31). `raise` means nothing loads these by accident: code that needs
    # them must ask for them explicitly, so the enquiry list never pays for them.
    reference_images: Mapped[list["EnquiryImage"]] = relationship(
        lazy="raise", order_by="EnquiryImage.id", cascade="all, delete-orphan", passive_deletes=True
    )
