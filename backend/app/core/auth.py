from datetime import UTC
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import jwt_configured, read_access_claims
from app.db.session import get_session
from app.models import AdminUser
from app.models.enums import AdminRole

_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AdminUser:
    """Guards every admin route (FR-51). The account is re-read from the database each time,
    so a deactivated or deleted admin loses access immediately, even with an unexpired token."""
    if credentials is None or not jwt_configured():
        raise _unauthorized()
    claims = read_access_claims(credentials.credentials)
    admin = await session.get(AdminUser, claims[0]) if claims is not None else None
    if admin is None or not admin.is_active:
        raise _unauthorized()
    if _issued_before_password_change(admin, issued_at=claims[1]):
        raise _unauthorized()  # a password change ends every earlier session (FR-56)
    return admin


def _issued_before_password_change(admin: AdminUser, issued_at: int) -> bool:
    changed = admin.password_changed_at
    if changed is None:
        return False
    if changed.tzinfo is None:  # SQLite hands back naive datetimes; PostgreSQL returns aware ones
        changed = changed.replace(tzinfo=UTC)
    # Whole seconds, because that is the precision of a token's issue time.
    return issued_at < int(changed.timestamp())


async def require_owner(admin: Annotated[AdminUser, Depends(get_current_admin)]) -> AdminUser:
    """For routes only an Owner may use, such as managing admin accounts (FR-57)."""
    if admin.role != AdminRole.owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Owner access required")
    return admin


CurrentAdmin = Annotated[AdminUser, Depends(get_current_admin)]
