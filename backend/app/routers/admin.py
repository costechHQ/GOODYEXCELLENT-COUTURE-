from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentAdmin
from app.core.config import settings
from app.core.security import burn_password_check, create_access_token, jwt_configured, verify_password
from app.db.session import get_session
from app.models import AdminUser
from app.schemas.admin import AdminOut, LoginIn, TokenOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, session: Annotated[AsyncSession, Depends(get_session)]):
    if not jwt_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Sign-in is not available")

    admin = await session.scalar(select(AdminUser).where(AdminUser.email == data.email.strip().lower()))
    if admin is None:
        burn_password_check(data.password)
        password_ok = False
    else:
        password_ok = verify_password(data.password, admin.password_hash)

    # One message for every failure, so it never says which part was wrong.
    if admin is None or not password_ok or not admin.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(access_token=create_access_token(admin.id), expires_in=settings.access_token_minutes * 60)


@router.get("/me", response_model=AdminOut)
async def who_am_i(admin: CurrentAdmin):
    return admin
