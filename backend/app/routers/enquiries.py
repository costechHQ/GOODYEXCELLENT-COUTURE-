from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Enquiry
from app.models.enums import EnquiryType
from app.schemas.enquiry import ConsultationIn, ContactIn, EnquiryReceived, LaundryIn, OrderIn

router = APIRouter(prefix="/enquiries", tags=["enquiries"])


@router.post("/consultation", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_consultation(data: ConsultationIn, session: Annotated[AsyncSession, Depends(get_session)]):
    enquiry = Enquiry(type=EnquiryType.consultation, **data.model_dump())
    session.add(enquiry)
    await session.commit()
    return EnquiryReceived(id=enquiry.id)


@router.post("/contact", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_contact_message(data: ContactIn, session: Annotated[AsyncSession, Depends(get_session)]):
    enquiry = Enquiry(type=EnquiryType.general, **data.model_dump())
    session.add(enquiry)
    await session.commit()
    return EnquiryReceived(id=enquiry.id)


@router.post("/laundry", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_laundry_enquiry(data: LaundryIn, session: Annotated[AsyncSession, Depends(get_session)]):
    enquiry = Enquiry(type=EnquiryType.laundry, **data.model_dump())
    session.add(enquiry)
    await session.commit()
    return EnquiryReceived(id=enquiry.id)


@router.post("/order", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_order_enquiry(data: OrderIn, session: Annotated[AsyncSession, Depends(get_session)]):
    enquiry = Enquiry(type=EnquiryType.order, **data.model_dump())
    session.add(enquiry)
    await session.commit()
    return EnquiryReceived(id=enquiry.id)
