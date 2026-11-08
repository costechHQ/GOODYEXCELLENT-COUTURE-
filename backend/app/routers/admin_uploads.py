from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.core.auth import get_current_admin
from app.core.config import settings
from app.core.storage import public_url
from app.core.uploads import MULTIPART_OVERHEAD, read_and_process, store, too_large_message

# Any signed-in admin may upload (FR-28, FR-51).
router = APIRouter(prefix="/admin/uploads", tags=["admin"], dependencies=[Depends(get_current_admin)])


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
    if declared and declared.isdigit() and int(declared) > limit + MULTIPART_OVERHEAD:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=too_large_message(limit))

    stored = await store(await read_and_process(file))

    urls = {str(width): public_url(name) for width, name in zip(stored.widths, stored.names, strict=True)}
    return ImageUploadOut(
        id=stored.image_id,
        url=urls[str(max(stored.widths))],
        variants=urls,
        width=stored.width,
        height=stored.height,
    )
