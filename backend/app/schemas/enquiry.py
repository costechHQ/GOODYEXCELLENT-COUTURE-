import re
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.models.enums import ContactMethod

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]

_NG_LOCAL = re.compile(r"^0[789][01]\d{8}$")  # 0806..., 0902...
_NG_INTL = re.compile(r"^\+?234([789][01]\d{8})$")
_INTL = re.compile(r"^\+[1-9]\d{7,14}$")


def normalise_phone(value: str) -> str:
    """Accept Nigerian (080..., +234...) and international numbers (FR-33); return E.164."""
    cleaned = re.sub(r"[\s\-().]", "", value)
    if _NG_LOCAL.match(cleaned):
        return "+234" + cleaned[1:]
    if m := _NG_INTL.match(cleaned):
        return "+234" + m.group(1)
    if _INTL.match(cleaned):
        return cleaned
    raise ValueError("Enter a valid phone number, e.g. 08012345678 or +2348012345678")


Phone = Annotated[str, Field(max_length=32)]


class EnquiryIn(BaseModel):
    """Shared fields. `website` is a honeypot: real visitors never see or fill it (FR-37)."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    phone: Phone | None = None
    email: EmailStr | None = None
    message: Message | None = None
    website: str = ""

    @model_validator(mode="after")
    def _normalise_phone(self):
        if self.phone is not None:
            self.phone = normalise_phone(self.phone)
        return self


class ConsultationIn(EnquiryIn):  # FR-30
    phone: Phone
    preferred_contact: ContactMethod
    service_id: int | None = None
    preferred_datetime: datetime | None = None


class OrderIn(EnquiryIn):  # FR-31
    phone: Phone
    preferred_contact: ContactMethod
    service_id: int | None = None
    gallery_item_id: int | None = None
    garment_type: ShortText
    occasion: ShortText | None = None
    needed_by: date | None = None
    quantity: int | None = Field(default=None, ge=1, le=1000)
    fabric_preference: ShortText | None = None


class LaundryIn(EnquiryIn):  # FR-42
    phone: Phone
    garment_types: ShortText


class ContactIn(EnquiryIn):  # FR-47: phone or email, plus subject and message
    subject: ShortText
    message: Message

    @model_validator(mode="after")
    def _needs_a_way_to_reply(self):
        if not self.phone and not self.email:
            raise ValueError("Provide a phone number or an email address")
        return self


class EnquiryReceipt(BaseModel):
    """FR-34: confirm receipt without promising a response time."""

    id: int | None = None
    message: str = "Thank you. GOODYEXCELLENT COUTURE has received your enquiry and will respond."
