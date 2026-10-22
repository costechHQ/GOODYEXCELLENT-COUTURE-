"""Public service listing and admin edits (FR-19 to FR-23, FR-52)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Service
from app.schemas.service import ServiceOut

router = APIRouter(prefix="/services", tags=["services"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[ServiceOut])
async def list_services(session: Session):
    query = select(Service).where(Service.visible).order_by(Service.display_order, Service.id)
    return (await session.scalars(query)).all()


@router.get("/{slug}", response_model=ServiceOut)
async def get_service(slug: str, session: Session):
    service = await session.scalar(select(Service).where(Service.slug == slug, Service.visible))
    if service is None:
        raise HTTPException(404, "Service not found")
    return service
