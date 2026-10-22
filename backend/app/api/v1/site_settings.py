"""Site-wide contact details, hours and social links (FR-44 to FR-48, FR-55)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import SiteSettings
from app.schemas.site_settings import SiteSettingsOut

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SiteSettingsOut)
async def get_settings(session: Annotated[AsyncSession, Depends(get_session)]):
    row = await session.get(SiteSettings, 1)
    if row is None:
        raise HTTPException(404, "Site settings have not been seeded")
    return row
