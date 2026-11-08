from datetime import UTC, date, datetime, timedelta, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

from app.core.phone import normalise_phone
from app.models.enums import ContactMethod, EnquiryStatus, EnquiryType

# Trim whitespace, so "  " counts as empty.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Garment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Occasion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Fabric = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Service = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class _FormBase(BaseModel):
    """Common to every public form."""

    # Reject unknown fields so a client can never set status, notes or type.
    model_config = ConfigDict(extra="forbid")

    # Honeypot (FR-37): hidden from people in the form, so only bots fill it in.
    # The router silently discards a submission where it is set. It is never stored.
    website: str | None = None


_WAT = timezone(timedelta(hours=1))  # Nigeria time, so "today" matches the visitor's calendar


def _today_in_nigeria() -> date:
    return datetime.now(UTC).astimezone(_WAT).date()


class _ContactDetails(_FormBase):
    """Fields and checks shared by the consultation and order forms (FR-30, FR-31)."""

    name: Name
    phone: str
    email: EmailStr | None = None
    preferred_contact: ContactMethod

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str:
        return normalise_phone(v)  # raises ValueError, reported against the "phone" field

    @model_validator(mode="after")
    def check_email_when_preferred(self):
        if self.preferred_contact == ContactMethod.email and not self.email:
            raise ValueError("An email address is required when email is the preferred contact method")
        return self


class ConsultationIn(_ContactDetails):
    """The consultation form (FR-30). No body measurements: those are taken in person (FR-38)."""

    service: Service | None = None
    preferred_at: datetime | None = None
    message: Message | None = None


class OrderIn(_ContactDetails):
    """The order-enquiry form (FR-31), text fields only. Reference images arrive with the upload feature."""

    garment_type: Garment
    occasion: Occasion | None = None
    needed_by: date | None = None
    quantity: int | None = Field(default=None, ge=1, le=500)
    fabric_preference: Fabric | None = None
    message: Message | None = None

    @field_validator("needed_by")
    @classmethod
    def not_in_the_past(cls, v: date | None) -> date | None:
        if v is not None and v < _today_in_nigeria():
            raise ValueError("The needed-by date cannot be in the past")
        return v


class ContactIn(_FormBase):
    """The general contact form (FR-47): name, phone or email, subject, message."""

    name: Name
    phone: str | None = None
    email: EmailStr | None = None
    subject: Subject
    message: Message

    @field_validator("phone", "email", mode="before")
    @classmethod
    def blank_means_not_provided(cls, v):
        # A form left empty is sent as "", which must count as missing.
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str | None) -> str | None:
        return None if v is None else normalise_phone(v)

    @model_validator(mode="after")
    def needs_a_way_to_reply(self):
        if not self.phone and not self.email:
            raise ValueError("Provide a phone number or an email address so we can reply")
        return self


class LaundryIn(_FormBase):
    """The laundry enquiry form (FR-42): name, phone, garment types, message."""

    name: Name
    phone: str
    garment_type: Garment
    message: Message | None = None

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str:
        return normalise_phone(v)


class EnquiryReceived(BaseModel):
    """FR-34: confirm receipt without promising a response time."""

    id: int
    message: str = Field(default="Thank you. We have received your request and will be in touch.")


# --- admin (FR-53) ----------------------------------------------------------


class EnquirySummary(BaseModel):
    """One row in the admin list: enough to triage, without the full message or notes."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: EnquiryType
    status: EnquiryStatus
    name: str
    phone: str | None
    email: str | None
    preferred_contact: ContactMethod | None
    service: str | None
    subject: str | None
    created_at: datetime


class EnquiryDetail(EnquirySummary):
    """The whole record, including the staff-only notes (FR-54)."""

    message: str | None
    preferred_at: datetime | None
    garment_type: str | None
    occasion: str | None
    needed_by: date | None
    quantity: int | None
    fabric_preference: str | None
    internal_notes: str | None


class EnquiryPage(BaseModel):
    items: list[EnquirySummary]
    total: int  # all matches, ignoring limit and offset, so the screen can page
    limit: int
    offset: int
