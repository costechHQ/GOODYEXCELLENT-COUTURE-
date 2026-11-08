from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_admin
from app.db.session import get_session
from app.models import SiteSettings
from app.schemas.site_settings import SiteSettingsOut, SiteSettingsUpdate

# Any signed-in admin may edit the site-wide contact details (FR-55, FR-51).
router = APIRouter(prefix="/admin/settings", tags=["admin"], dependencies=[Depends(get_current_admin)])


@router.patch("", response_model=SiteSettingsOut)
async def update_settings(data: SiteSettingsUpdate, session: Annotated[AsyncSession, Depends(get_session)]):
    settings_row = await session.get(SiteSettings, 1)
    if settings_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Site settings have not been set up yet")
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(settings_row, name, value)
    await session.commit()
    await session.refresh(settings_row)
    return settings_row
