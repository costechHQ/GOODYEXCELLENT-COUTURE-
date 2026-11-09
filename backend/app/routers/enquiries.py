from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mail import notify_new_enquiry
from app.core.rate_limit import limit_enquiries
from app.core.uploads import (
    MAX_ORDER_IMAGES,
    ORDER_IMAGE_MAX_PIXELS,
    StoredImage,
    discard,
    read_and_process,
    store,
)
from app.db.session import get_session
from app.models import Enquiry, EnquiryImage
from app.models.enums import EnquiryType
from app.schemas.enquiry import (
    ConsultationIn,
    ContactIn,
    EnquiryReceived,
    LaundryIn,
    OrderIn,
    _FormBase,
)

router = APIRouter(prefix="/enquiries", tags=["enquiries"], dependencies=[Depends(limit_enquiries)])

Session = Annotated[AsyncSession, Depends(get_session)]


async def _save(
    session: AsyncSession,
    background: BackgroundTasks,
    kind: EnquiryType,
    data: _FormBase,
    images: list[StoredImage] | None = None,
) -> EnquiryReceived:
    if data.website:
        # Honeypot tripped (FR-37): a bot filled the hidden field. Answer exactly like a
        # success so it learns nothing, but store nothing.
        return EnquiryReceived(id=0)
    fields = data.model_dump(exclude={"website"})
    enquiry = Enquiry(type=kind, **fields)
    session.add(enquiry)
    if images:
        await session.flush()  # gives the enquiry its id, inside the same transaction
        session.add_all(
            EnquiryImage(enquiry_id=enquiry.id, image_id=i.image_id, width=i.width, height=i.height, widths=i.widths)
            for i in images
        )
    await session.commit()
    # Saved first; the email goes out after the response is sent, and cannot lose the enquiry (NFR-15).
    mail_fields = fields | ({"reference_images": f"{len(images)} (see the admin area)"} if images else {})
    background.add_task(notify_new_enquiry, enquiry.id, kind.value, mail_fields)
    return EnquiryReceived(id=enquiry.id)


@router.post("/consultation", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_consultation(data: ConsultationIn, session: Session, background: BackgroundTasks):
    return await _save(session, background, EnquiryType.consultation, data)


@router.post("/order", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_order_enquiry(
    data: Annotated[OrderIn, Form()],
    session: Session,
    background: BackgroundTasks,
    # `str` is accepted only because a browser with no file chosen sends a part with an empty file
    # name, which Starlette delivers as an empty string rather than a file.
    images: list[UploadFile | str] | None = None,
):
    """The order form with up to five reference pictures (FR-31), sent as one multipart request.
    Everything is saved together or nothing is: a bad picture means no enquiry and no files."""
    if data.website:
        return EnquiryReceived(id=0)  # a bot: do no image work at all

    files: list[UploadFile] = []
    for part in images or []:
        if isinstance(part, str):
            if part.strip():  # real text sent in the files field is a mistake, not "no file chosen"
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Reference images must be files.")
            continue
        if part.filename or part.size:
            files.append(part)
    if len(files) > MAX_ORDER_IMAGES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"You can attach up to {MAX_ORDER_IMAGES} images.")

    # Check every picture before writing anything, so a bad one leaves nothing behind.
    processed = [
        await read_and_process(f, max_pixels=ORDER_IMAGE_MAX_PIXELS, label=f"Reference image {number}")
        for number, f in enumerate(files, start=1)
    ]

    stored: list[StoredImage] = []
    try:
        for picture in processed:
            stored.append(await store(picture))
        return await _save(session, background, EnquiryType.order, data, stored)
    except BaseException:
        for picture in stored:  # the enquiry did not save, so its files must not stay behind
            await discard(picture)
        raise


@router.post("/laundry", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_laundry_enquiry(data: LaundryIn, session: Session, background: BackgroundTasks):
    return await _save(session, background, EnquiryType.laundry, data)


@router.post("/contact", response_model=EnquiryReceived, status_code=status.HTTP_201_CREATED)
async def create_contact_message(data: ContactIn, session: Session, background: BackgroundTasks):
    return await _save(session, background, EnquiryType.general, data)
