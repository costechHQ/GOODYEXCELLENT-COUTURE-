from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

from app.core.phone import normalise_phone
from app.models.enums import ContactMethod

# Trim whitespace, so "  " counts as empty.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Garment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Service = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class ConsultationIn(BaseModel):
    """The consultation form (FR-30). No body measurements: those are taken in person (FR-38)."""

    # Reject unknown fields so a client can never set status, notes or type.
    model_config = ConfigDict(extra="forbid")

    name: Name
    phone: str
    email: EmailStr | None = None
    preferred_contact: ContactMethod
    service: Service | None = None
    preferred_at: datetime | None = None
    message: Message | None = None

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str:
        return normalise_phone(v)  # raises ValueError, reported against the "phone" field

    @model_validator(mode="after")
    def check_email_when_preferred(self):
        if self.preferred_contact == ContactMethod.email and not self.email:
            raise ValueError("An email address is required when email is the preferred contact method")
        return self


class ContactIn(BaseModel):
    """The general contact form (FR-47): name, phone or email, subject, message."""

    model_config = ConfigDict(extra="forbid")

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


class LaundryIn(BaseModel):
    """The laundry enquiry form (FR-42): name, phone, garment types, message."""

    model_config = ConfigDict(extra="forbid")

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
