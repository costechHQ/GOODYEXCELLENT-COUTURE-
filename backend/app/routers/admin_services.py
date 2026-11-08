from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_admin
from app.db.session import get_session
from app.models import Service
from app.schemas.service import ServiceAdminOut, ServiceUpdate

# Owner and Staff may both edit services text (FR-52); everything here needs a signed-in admin (FR-51).
router = APIRouter(prefix="/admin/services", tags=["admin"], dependencies=[Depends(get_current_admin)])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[ServiceAdminOut])
async def list_all_services(session: Session):
    """Every service, hidden ones included, so an admin can find and unhide them."""
    return (await session.scalars(select(Service).order_by(Service.display_order, Service.id))).all()


@router.patch("/{service_id}", response_model=ServiceAdminOut)
async def update_service(service_id: int, data: ServiceUpdate, session: Session):
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Service not found")
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(service, name, value)
    await session.commit()
    await session.refresh(service)
    return service
