from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_admin
from app.db.session import get_session
from app.models import Enquiry
from app.models.enums import EnquiryStatus, EnquiryType
from app.schemas.enquiry import EnquiryDetail, EnquiryPage

# Enquiries hold clients' personal details, so every route needs a signed-in admin (FR-51, FR-53).
router = APIRouter(prefix="/admin/enquiries", tags=["admin"], dependencies=[Depends(get_current_admin)])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=EnquiryPage)
async def list_enquiries(
    session: Session,
    type: EnquiryType | None = None,
    status: EnquiryStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filters = []
    if type is not None:
        filters.append(Enquiry.type == type)
    if status is not None:
        filters.append(Enquiry.status == status)

    total = await session.scalar(select(func.count()).select_from(Enquiry).where(*filters))
    query = (
        select(Enquiry)
        .where(*filters)
        .order_by(Enquiry.created_at.desc(), Enquiry.id.desc())  # newest first
        .limit(limit)
        .offset(offset)
    )
    items = (await session.scalars(query)).all()
    return EnquiryPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{enquiry_id}", response_model=EnquiryDetail)
async def get_enquiry(enquiry_id: int, session: Session):
    enquiry = await session.get(Enquiry, enquiry_id)
    if enquiry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Enquiry not found")
    return enquiry
