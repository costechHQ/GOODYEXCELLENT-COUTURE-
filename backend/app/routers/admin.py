from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentAdmin
from app.core.config import settings
from app.core.rate_limit import limit_logins
from app.core.security import burn_password_check, create_access_token, jwt_configured, verify_password
from app.db.session import get_session
from app.models import AdminUser
from app.schemas.admin import AdminOut, LoginIn, TokenOut

router = APIRouter(prefix="/admin", tags=["admin"])


def _is_locked(admin: AdminUser) -> bool:
    if admin.locked_until is None:
        return False
    until = admin.locked_until
    if until.tzinfo is None:  # SQLite hands back naive datetimes; PostgreSQL returns aware ones
        until = until.replace(tzinfo=UTC)
    return until > datetime.now(UTC)


async def _record_failure(session: AsyncSession, admin: AdminUser) -> None:
    # Increment inside the database so two simultaneous guesses are both counted.
    await session.execute(
        update(AdminUser)
        .where(AdminUser.id == admin.id)
        .values(failed_login_attempts=AdminUser.failed_login_attempts + 1)
    )
    await session.refresh(admin)
    if admin.failed_login_attempts >= settings.login_max_failures:
        admin.locked_until = datetime.now(UTC) + timedelta(minutes=settings.login_lock_minutes)
        admin.failed_login_attempts = 0
    await session.commit()


@router.post("/login", response_model=TokenOut, dependencies=[Depends(limit_logins)])
async def login(data: LoginIn, session: Annotated[AsyncSession, Depends(get_session)]):
    if not jwt_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Sign-in is not available")

    admin = await session.scalar(select(AdminUser).where(AdminUser.email == data.email.strip().lower()))

    if admin is None:
        burn_password_check(data.password)
        succeeded = False
    elif _is_locked(admin):
        # Locked: refuse even the right password, without counting or extending the lock, and
        # without any sign that a lock exists. Spend the same time as a real check.
        burn_password_check(data.password)
        succeeded = False
    elif not verify_password(data.password, admin.password_hash):
        await _record_failure(session, admin)
        succeeded = False
    else:
        succeeded = admin.is_active
        if succeeded:
            admin.failed_login_attempts = 0
            admin.locked_until = None
            await session.commit()

    # One message for every failure, so it never says which part was wrong.
    if not succeeded:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(access_token=create_access_token(admin.id), expires_in=settings.access_token_minutes * 60)


@router.get("/me", response_model=AdminOut)
async def who_am_i(admin: CurrentAdmin):
    return admin
