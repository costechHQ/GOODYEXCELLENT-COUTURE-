"""Public gallery with category filter and admin upload (FR-24 to FR-29)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import GalleryItem
from app.models.enums import GalleryCategory
from app.schemas.gallery import GalleryItemOut

router = APIRouter(prefix="/gallery", tags=["gallery"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[GalleryItemOut])
async def list_gallery(
    session: Session,
    category: GalleryCategory | None = None,
    featured: bool | None = None,
    service_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    query = select(GalleryItem).order_by(GalleryItem.display_order, GalleryItem.id)
    if category is not None:
        query = query.where(GalleryItem.category == category)
    if featured is not None:
        query = query.where(GalleryItem.featured == featured)
    if service_id is not None:
        query = query.where(GalleryItem.service_id == service_id)
    return (await session.scalars(query.limit(limit).offset(offset))).all()
