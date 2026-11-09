from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_admin
from app.core.media_cleanup import release_image
from app.db.session import get_session
from app.models import Testimonial
from app.schemas.testimonial import (
    TestimonialAdminOut,
    TestimonialCreate,
    TestimonialUpdate,
)

# Owner and Staff may both manage testimonials (FR-50); everything here needs a signed-in admin (FR-51).
router = APIRouter(prefix="/admin/testimonials", tags=["admin"], dependencies=[Depends(get_current_admin)])

Session = Annotated[AsyncSession, Depends(get_session)]


async def _get_or_404(session: AsyncSession, testimonial_id: int) -> Testimonial:
    testimonial = await session.get(Testimonial, testimonial_id)
    if testimonial is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Testimonial not found")
    return testimonial


@router.get("", response_model=list[TestimonialAdminOut])
async def list_all_testimonials(session: Session):
    """Every testimonial, hidden ones included, newest first (the same order as the public list)."""
    return (await session.scalars(select(Testimonial).order_by(Testimonial.id.desc()))).all()


@router.post("", response_model=TestimonialAdminOut, status_code=status.HTTP_201_CREATED)
async def create_testimonial(data: TestimonialCreate, session: Session):
    testimonial = Testimonial(**data.model_dump())
    session.add(testimonial)
    await session.commit()
    await session.refresh(testimonial)  # loads created_at, which the database fills in
    return testimonial


@router.patch("/{testimonial_id}", response_model=TestimonialAdminOut)
async def update_testimonial(testimonial_id: int, data: TestimonialUpdate, session: Session):
    testimonial = await _get_or_404(session, testimonial_id)
    old_url = testimonial.photo_url
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(testimonial, name, value)
    await session.commit()
    await session.refresh(testimonial)
    if testimonial.photo_url != old_url:
        await release_image(session, old_url)  # the replaced or removed photo, if nothing else uses it
    return testimonial


@router.delete("/{testimonial_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_testimonial(testimonial_id: int, session: Session):
    testimonial = await _get_or_404(session, testimonial_id)
    old_url = testimonial.photo_url
    await session.delete(testimonial)
    await session.commit()
    await release_image(session, old_url)  # only after the row is really gone
    return Response(status_code=status.HTTP_204_NO_CONTENT)
