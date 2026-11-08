from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

from app.core.phone import normalise_phone
from app.models.enums import ContactMethod

# Trim whitespace, so "  " counts as empty.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
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


class EnquiryReceived(BaseModel):
    """FR-34: confirm receipt without promising a response time."""

    id: int
    message: str = Field(default="Thank you. We have received your request and will be in touch.")
