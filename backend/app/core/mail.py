import logging
import smtplib
import ssl
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_LABELS = {
    "name": "Name",
    "phone": "Phone",
    "email": "Email",
    "preferred_contact": "Preferred contact",
    "service": "Service",
    "subject": "Subject",
    "preferred_at": "Preferred date and time",
    "garment_type": "Garment type",
    "occasion": "Occasion",
    "needed_by": "Needed by",
    "quantity": "Quantity",
    "fabric_preference": "Fabric or colour",
    "message": "Message",
}
_SMTP_TIMEOUT_SECONDS = 10


def mail_enabled() -> bool:
    """Mail is sent only when a server and a recipient are configured."""
    return bool(settings.smtp_host and settings.enquiry_notify_to)


def build_enquiry_message(enquiry_id: int, kind: str, fields: dict[str, Any]) -> EmailMessage:
    """Plain-text alert for the brand's enquiry inbox (FR-35).

    EmailMessage refuses newlines in headers, which blocks header injection through visitor text;
    the subject is also flattened to one short line.
    """
    name = " ".join(str(fields.get("name", "")).split())[:60]
    msg = EmailMessage()
    msg["Subject"] = f"[New {kind} enquiry] {name}"
    msg["From"] = settings.mail_from or settings.enquiry_notify_to
    msg["To"] = settings.enquiry_notify_to
    if fields.get("email"):
        msg["Reply-To"] = str(fields["email"])  # replying goes straight to the client

    lines = [f"A new {kind} enquiry (#{enquiry_id}) arrived on {datetime.now(UTC):%d %b %Y at %H:%M} UTC.", ""]
    lines += [f"{label}: {fields[key]}" for key, label in _LABELS.items() if fields.get(key) not in (None, "")]
    lines += ["", "Follow up by phone, WhatsApp or email, then update its status in the admin area."]
    msg.set_content("\n".join(lines))
    return msg


def _send(msg: EmailMessage) -> None:
    if settings.smtp_security == "ssl":
        smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=_SMTP_TIMEOUT_SECONDS,
                                context=ssl.create_default_context())  # fmt: skip
    else:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=_SMTP_TIMEOUT_SECONDS)
    with smtp:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        smtp.send_message(msg)


def smtp_configured() -> bool:
    """Enough settings to send mail to someone other than the enquiry inbox."""
    return bool(settings.smtp_host and (settings.mail_from or settings.enquiry_notify_to))


def build_password_reset_message(to: str, token: str) -> EmailMessage:
    """The reset email (FR-56). The token travels in the link's fragment (#token=...), which
    browsers never send to servers, so it stays out of access logs and Referer headers."""
    link = f"{settings.frontend_url.rstrip('/')}/admin/reset-password#token={token}"
    msg = EmailMessage()
    msg["Subject"] = "Reset your GOODYEXCELLENT COUTURE admin password"
    msg["From"] = settings.mail_from or settings.enquiry_notify_to
    msg["To"] = to  # EmailMessage refuses a newline here, so it cannot be used to inject headers
    msg.set_content(
        "Someone asked to reset the password for this admin account.\n\n"
        f"To choose a new password, open this link within {settings.password_reset_minutes} minutes. "
        "It works only once:\n\n"
        f"{link}\n\n"
        "If you did not ask for this, ignore this email. Your password has not changed."
    )
    return msg


def notify_password_reset(to: str, token: str) -> None:
    """Background task. A failure is logged without the address or the token, and never reaches
    the visitor: the request route answers the same way whatever happens here."""
    if not smtp_configured():
        logger.warning("A password reset was requested but email is not configured; nothing was sent")
        return
    try:
        _send(build_password_reset_message(to, token))
    except Exception as exc:
        logger.error("A password reset email could not be sent (%s)", type(exc).__name__)


def notify_new_enquiry(enquiry_id: int, kind: str, fields: dict[str, Any]) -> None:
    """Background task. By now the enquiry is already saved, so a failure here must never
    surface to the visitor or lose data (NFR-15). It is logged without the visitor's details."""
    if not mail_enabled():
        return
    try:
        _send(build_enquiry_message(enquiry_id, kind, fields))
    except Exception as exc:
        logger.error("Enquiry #%s saved, but the notification email failed (%s)", enquiry_id, type(exc).__name__)
