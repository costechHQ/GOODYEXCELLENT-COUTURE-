from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Enquiry
from app.models.enums import EnquiryType
from app.schemas.enquiry import ConsultationIn, ContactIn, EnquiryReceived, LaundryIn, OrderIn, _FormBase

router = APIRouter(prefix="/enquiries", tags=["enquiries"])

Session = Annotated[AsyncSession, Depends(get_session)]


async def _save(session: AsyncSession, kind: EnquiryType, data: _FormBase) -> EnquiryReceived:
    if data.website:
        # Honeypot tripped (FR-37): a bot filled the hidden field. Answer exactly like a
        # success so it learns nothing, but store nothing.
        return EnquiryReceived(id=0)
    enquiry = Enquiry(type=kind, **data.model_dump(exclude={"website"}))
    session.add(enquiry)
    await session.commit()
    return EnquiryReceived(id=enquiry.id)


@router.post("/consultation", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_consultation(data: ConsultationIn, session: Session):
    return await _save(session, EnquiryType.consultation, data)


@router.post("/order", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_order_enquiry(data: OrderIn, session: Session):
    return await _save(session, EnquiryType.order, data)


@router.post("/laundry", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_laundry_enquiry(data: LaundryIn, session: Session):
    return await _save(session, EnquiryType.laundry, data)


@router.post("/contact", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_contact_message(data: ContactIn, session: Session):
    return await _save(session, EnquiryType.general, data)
