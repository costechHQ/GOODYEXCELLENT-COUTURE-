"""Reading, checking and storing uploaded pictures. Shared by the admin upload route and the public
order form, so both enforce exactly the same rules (FR-29, FR-31)."""

from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.images import MAX_PIXELS, ImageRejected, ProcessedImage, process_image
from app.core.storage import get_storage

MULTIPART_OVERHEAD = 64 * 1024  # the form wrapper around the files

# The public order form (FR-31): up to five reference pictures. Their size limit is the same as the
# admin's, but the pixel cap is lower because this route is open to everyone and decoding is costly.
MAX_ORDER_IMAGES = 5
ORDER_IMAGE_MAX_PIXELS = 16_000_000


@dataclass
class StoredImage:
    image_id: str
    width: int
    height: int
    widths: list[int]  # the sizes written, smallest first

    @property
    def names(self) -> list[str]:
        return [f"{self.image_id}-{w}.webp" for w in self.widths]


def too_large_message(limit: int) -> str:
    return f"That file is too large. The limit is {limit // (1024 * 1024)} MB."


async def read_and_process(file: UploadFile, *, max_pixels: int = MAX_PIXELS, label: str = "") -> ProcessedImage:
    """Read the upload (never more than one byte past the size limit) and turn it into WebP sizes.
    Raises HTTPException with a clear message if it cannot be used. `label` prefixes the message
    when several files are sent, for example "Reference image 2"."""
    prefix = f"{label}: " if label else ""
    limit = settings.max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=prefix + too_large_message(limit))
    try:
        # Decoding and resizing are slow, so they run off the event loop and never stall other visitors.
        return await run_in_threadpool(process_image, data, max_pixels)
    except ImageRejected as rejected:
        raise HTTPException(rejected.status, detail=prefix + rejected.reason) from None


async def store(processed: ProcessedImage) -> StoredImage:
    """Write every size to storage under a random id. If anything fails, remove what was written."""
    stored = StoredImage(
        image_id=uuid4().hex,  # random, so addresses cannot be guessed
        width=processed.width,
        height=processed.height,
        widths=sorted(processed.variants),
    )
    storage = get_storage()
    try:
        for width, name in zip(stored.widths, stored.names, strict=True):
            await run_in_threadpool(storage.save, name, processed.variants[width])
    except OSError:
        await discard(stored)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="The image could not be saved") from None
    return stored


async def discard(stored: StoredImage) -> None:
    """Delete a stored image's files, for example when the enquiry it belonged to failed to save."""
    storage = get_storage()
    for name in stored.names:
        await run_in_threadpool(storage.delete, name)
