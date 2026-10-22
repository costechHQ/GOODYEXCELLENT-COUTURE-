"""Enquiry submission (FR-30 to FR-38, FR-42, FR-47, FR-58). Admin management comes later."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_session
from app.models import Enquiry, GalleryItem, Service
from app.models.enums import EnquiryType
from app.schemas.enquiry import (
    ConsultationIn,
    ContactIn,
    EnquiryIn,
    EnquiryReceipt,
    LaundryIn,
    OrderIn,
)
from app.services.email import send_enquiry_notification

router = APIRouter(prefix="/enquiries", tags=["enquiries"])

Session = Annotated[AsyncSession, Depends(get_session)]


async def _create(
    session: AsyncSession,
    background: BackgroundTasks,
    kind: EnquiryType,
    data: EnquiryIn,
    **extra,
) -> EnquiryReceipt:
    if data.website:  # honeypot tripped: look successful, store nothing (FR-37)
        return EnquiryReceipt()

    service_id = extra.get("service_id")
    if service_id is not None and await session.get(Service, service_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown service")
    item_id = extra.get("gallery_item_id")
    if item_id is not None and await session.get(GalleryItem, item_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown gallery item")

    enquiry = Enquiry(
        type=kind,
        name=data.name,
        phone=data.phone,
        email=data.email,
        message=data.message,
        **extra,
    )
    session.add(enquiry)
    await session.commit()  # saved before any email is attempted (NFR-15)

    background.add_task(send_enquiry_notification, enquiry.id)
    return EnquiryReceipt(id=enquiry.id)


def _fields(data: EnquiryIn, *exclude: str) -> dict:
    skip = {"name", "phone", "email", "message", "website", *exclude}
    return data.model_dump(exclude=skip)


@router.post("/consultation", response_model=EnquiryReceipt, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.enquiry_rate_limit)
async def create_consultation(
    request: Request, data: ConsultationIn, session: Session, background: BackgroundTasks
):
    return await _create(session, background, EnquiryType.consultation, data, **_fields(data))


@router.post("/order", response_model=EnquiryReceipt, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.enquiry_rate_limit)
async def create_order(
    request: Request, data: OrderIn, session: Session, background: BackgroundTasks
):
    return await _create(session, background, EnquiryType.order, data, **_fields(data))


@router.post("/laundry", response_model=EnquiryReceipt, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.enquiry_rate_limit)
async def create_laundry(
    request: Request, data: LaundryIn, session: Session, background: BackgroundTasks
):
    return await _create(
        session, background, EnquiryType.laundry, data, garment_type=data.garment_types
    )


@router.post("/contact", response_model=EnquiryReceipt, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.enquiry_rate_limit)
async def create_contact(
    request: Request, data: ContactIn, session: Session, background: BackgroundTasks
):
    return await _create(session, background, EnquiryType.general, data, subject=data.subject)
