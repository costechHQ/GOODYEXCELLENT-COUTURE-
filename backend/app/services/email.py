"""Background email sending (TS-04, FR-35, FR-58, NFR-15).

The enquiry is committed to the database first; the email is sent afterwards as a
background task, so a mail failure never loses the enquiry.
"""

import logging
from datetime import UTC, datetime
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Enquiry

log = logging.getLogger(__name__)


def build_notification(enquiry: Enquiry) -> EmailMessage:
    contact = enquiry.preferred_contact.value if enquiry.preferred_contact else "-"
    lines = [
        f"New {enquiry.type.value} enquiry #{enquiry.id}",
        f"Name: {enquiry.name}",
        f"Phone: {enquiry.phone or '-'}",
        f"Email: {enquiry.email or '-'}",
        f"Preferred contact: {contact}",
    ]
    for label, value in (
        ("Subject", enquiry.subject),
        ("Garment", enquiry.garment_type),
        ("Occasion", enquiry.occasion),
        ("Needed by", enquiry.needed_by),
        ("Quantity", enquiry.quantity),
        ("Fabric/colour", enquiry.fabric_preference),
        ("Preferred time", enquiry.preferred_datetime),
        ("Message", enquiry.message),
    ):
        if value:
            lines.append(f"{label}: {value}")

    msg = EmailMessage()  # plain text only, so visitor input is never rendered as HTML
    msg["From"] = str(settings.mail_from)
    msg["To"] = str(settings.enquiry_email)
    msg["Subject"] = (
        f"[GOODYEXCELLENT COUTURE] New {enquiry.type.value} enquiry from {enquiry.name}"
    )
    if enquiry.email:
        msg["Reply-To"] = enquiry.email
    msg.set_content("\n".join(lines))
    return msg


async def send_message(msg: EmailMessage) -> None:
    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=settings.smtp_use_tls,
    )


async def send_enquiry_notification(enquiry_id: int) -> None:
    """Runs after the response. Never raises: the enquiry is already saved (NFR-15)."""
    try:
        async with SessionLocal() as session:
            enquiry = await session.get(Enquiry, enquiry_id)
            if enquiry is None:
                return
            await send_message(build_notification(enquiry))
            enquiry.email_sent_at = datetime.now(UTC)
            await session.commit()
    except Exception:
        log.exception("Enquiry %s saved but notification email failed", enquiry_id)
