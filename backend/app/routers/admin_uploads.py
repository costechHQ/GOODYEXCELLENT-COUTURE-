from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.core.auth import get_current_admin
from app.core.config import settings
from app.core.images import ImageRejected, process_image
from app.core.storage import get_storage, public_url

# Any signed-in admin may upload (FR-28, FR-51).
router = APIRouter(prefix="/admin/uploads", tags=["admin"], dependencies=[Depends(get_current_admin)])

_MULTIPART_OVERHEAD = 64 * 1024  # the form wrapper around the file


class ImageUploadOut(BaseModel):
    id: str
    url: str  # the largest size: use this as a gallery item's image_url
    variants: dict[str, str]  # width in pixels -> address, for responsive pictures
    width: int
    height: int


@router.post("/images", response_model=ImageUploadOut, status_code=status.HTTP_201_CREATED)
async def upload_image(file: UploadFile, request: Request):
    limit = settings.max_upload_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit + _MULTIPART_OVERHEAD:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=_too_large(limit))
    data = await file.read(limit + 1)  # never reads more than one byte past the limit
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=_too_large(limit))

    try:
        # Decoding and resizing are slow, so they run off the event loop and never stall other visitors.
        processed = await run_in_threadpool(process_image, data)
    except ImageRejected as rejected:
        raise HTTPException(rejected.status, detail=rejected.reason) from None

    image_id = uuid4().hex  # random, so addresses cannot be guessed
    storage = get_storage()
    names = {width: f"{image_id}-{width}.webp" for width in processed.variants}
    try:
        for width, name in names.items():
            await run_in_threadpool(storage.save, name, processed.variants[width])
    except OSError:
        for name in names.values():  # do not leave half an upload behind
            await run_in_threadpool(storage.delete, name)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="The image could not be saved") from None

    urls = {str(width): public_url(name) for width, name in names.items()}
    return ImageUploadOut(
        id=image_id,
        url=urls[str(max(names))],
        variants=urls,
        width=processed.width,
        height=processed.height,
    )


def _too_large(limit: int) -> str:
    return f"That file is too large. The limit is {limit // (1024 * 1024)} MB."
