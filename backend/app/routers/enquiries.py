from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mail import notify_new_enquiry
from app.core.rate_limit import limit_enquiries
from app.db.session import get_session
from app.models import Enquiry
from app.models.enums import EnquiryType
from app.schemas.enquiry import ConsultationIn, ContactIn, EnquiryReceived, LaundryIn, OrderIn, _FormBase

router = APIRouter(prefix="/enquiries", tags=["enquiries"], dependencies=[Depends(limit_enquiries)])

Session = Annotated[AsyncSession, Depends(get_session)]


async def _save(
    session: AsyncSession, background: BackgroundTasks, kind: EnquiryType, data: _FormBase
) -> EnquiryReceived:
    if data.website:
        # Honeypot tripped (FR-37): a bot filled the hidden field. Answer exactly like a
        # success so it learns nothing, but store nothing.
        return EnquiryReceived(id=0)
    fields = data.model_dump(exclude={"website"})
    enquiry = Enquiry(type=kind, **fields)
    session.add(enquiry)
    await session.commit()
    # Saved first; the email goes out after the response is sent, and cannot lose the enquiry (NFR-15).
    background.add_task(notify_new_enquiry, enquiry.id, kind.value, fields)
    return EnquiryReceived(id=enquiry.id)


@router.post("/consultation", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_consultation(data: ConsultationIn, session: Session, background: BackgroundTasks):
    return await _save(session, background, EnquiryType.consultation, data)


@router.post("/order", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_order_enquiry(data: OrderIn, session: Session, background: BackgroundTasks):
    return await _save(session, background, EnquiryType.order, data)


@router.post("/laundry", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_laundry_enquiry(data: LaundryIn, session: Session, background: BackgroundTasks):
    return await _save(session, background, EnquiryType.laundry, data)


@router.post("/contact", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_contact_message(data: ContactIn, session: Session, background: BackgroundTasks):
    return await _save(session, background, EnquiryType.general, data)
