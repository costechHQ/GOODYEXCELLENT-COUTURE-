from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.mail import notify_password_reset
from app.core.rate_limit import limit_password_resets
from app.core.security import hash_password, hash_reset_token, new_reset_token
from app.db.session import get_session
from app.models import AdminUser, PasswordResetToken
from app.schemas.admin import MessageOut, PasswordResetConfirmIn, PasswordResetRequestIn

# Public on purpose: the person asking has forgotten their password, so cannot sign in (FR-56).
# A per-IP limit stops it being used to flood an admin's inbox or to guess links.
router = APIRouter(prefix="/admin/password-reset", tags=["admin"], dependencies=[Depends(limit_password_resets)])

Session = Annotated[AsyncSession, Depends(get_session)]

# The same words whether or not the address belongs to an admin, so this route can never be used
# to find out who the admins are.
_REQUEST_ANSWER = "If that address belongs to an admin account, a reset link has been sent to it."
_INVALID_LINK = "This reset link is invalid or has expired. Please ask for a new one."


def _aware(moment: datetime) -> datetime:
    # SQLite hands back naive datetimes; PostgreSQL returns aware ones.
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


@router.post("/request", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
async def request_reset(data: PasswordResetRequestIn, session: Session, background: BackgroundTasks):
    now = datetime.now(UTC)
    await session.execute(delete(PasswordResetToken).where(PasswordResetToken.expires_at < now))  # housekeeping

    admin = await session.scalar(select(AdminUser).where(AdminUser.email == data.email.strip().lower()))
    if admin is not None and admin.is_active:
        # Only the newest link works: asking again cancels the earlier one.
        await session.execute(delete(PasswordResetToken).where(PasswordResetToken.admin_id == admin.id))
        token, token_hash = new_reset_token()
        session.add(
            PasswordResetToken(
                admin_id=admin.id,
                token_hash=token_hash,
                expires_at=now + timedelta(minutes=settings.password_reset_minutes),
            )
        )
        background.add_task(notify_password_reset, admin.email, token)  # sent after the response
    await session.commit()
    return MessageOut(message=_REQUEST_ANSWER)


@router.post("/confirm", response_model=MessageOut)
async def confirm_reset(data: PasswordResetConfirmIn, session: Session):
    now = datetime.now(UTC)
    row = await session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(data.token))
    )
    admin = await session.get(AdminUser, row.admin_id) if row is not None else None
    if (
        row is None
        or row.used_at is not None
        or _aware(row.expires_at) <= now
        or admin is None
        or not admin.is_active
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=_INVALID_LINK)

    # Claim the link atomically: if two requests arrive together, only one changes the row.
    claimed = await session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.id == row.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    if claimed.rowcount != 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=_INVALID_LINK)

    admin.password_hash = hash_password(data.new_password)
    admin.password_changed_at = now  # every sign-in token issued before now stops working
    admin.failed_login_attempts = 0  # recovering the account also lifts any lockout
    admin.locked_until = None
    await session.execute(
        delete(PasswordResetToken).where(PasswordResetToken.admin_id == admin.id, PasswordResetToken.id != row.id)
    )
    await session.commit()
    return MessageOut(message="Your password has been updated. You can now sign in.")
