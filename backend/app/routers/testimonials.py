from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Testimonial
from app.schemas.testimonial import TestimonialOut

router = APIRouter(prefix="/testimonials", tags=["testimonials"])


@router.get("", response_model=list[TestimonialOut])
async def list_testimonials(session: Annotated[AsyncSession, Depends(get_session)]):
    # Only owner-approved testimonials are ever public (FR-49).
    query = select(Testimonial).where(Testimonial.visible).order_by(Testimonial.id.desc())
    return (await session.scalars(query)).all()
