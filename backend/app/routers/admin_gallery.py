from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_admin
from app.core.media_cleanup import release_image
from app.db.session import get_session
from app.models import GalleryItem
from app.schemas.gallery import GalleryItemAdminOut, GalleryItemCreate, GalleryItemUpdate

# Owner and Staff may both manage the gallery (FR-52); everything here needs a signed-in admin (FR-51).
router = APIRouter(prefix="/admin/gallery", tags=["admin"], dependencies=[Depends(get_current_admin)])

Session = Annotated[AsyncSession, Depends(get_session)]


async def _get_or_404(session: AsyncSession, item_id: int) -> GalleryItem:
    item = await session.get(GalleryItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Gallery item not found")
    return item


@router.post("", response_model=GalleryItemAdminOut, status_code=status.HTTP_201_CREATED)
async def create_item(data: GalleryItemCreate, session: Session):
    fields = data.model_dump()
    if fields["display_order"] is None:
        last = await session.scalar(select(func.max(GalleryItem.display_order)))
        fields["display_order"] = 0 if last is None else last + 1
    item = GalleryItem(**fields)
    session.add(item)
    await session.commit()
    await session.refresh(item)  # loads created_at, which the database fills in
    return item


@router.patch("/{item_id}", response_model=GalleryItemAdminOut)
async def update_item(item_id: int, data: GalleryItemUpdate, session: Session):
    item = await _get_or_404(session, item_id)
    old_url = item.image_url
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(item, name, value)
    await session.commit()
    await session.refresh(item)
    if item.image_url != old_url:
        await release_image(session, old_url)  # the replaced picture, if nothing else uses it
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int, session: Session):
    item = await _get_or_404(session, item_id)
    old_url = item.image_url
    await session.delete(item)
    await session.commit()
    await release_image(session, old_url)  # only after the row is really gone
    return Response(status_code=status.HTTP_204_NO_CONTENT)
