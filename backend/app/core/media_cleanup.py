"""Deleting stored pictures that nothing uses any more, so uploads do not pile up forever.

Call `release_image` AFTER the database change has been committed: the files go only once the rows
that pointed at them are gone, and a failed save therefore never costs anyone their pictures.
"""

import logging

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import get_storage, image_id_from_url
from app.models import EnquiryImage, GalleryItem, Service, Testimonial

logger = logging.getLogger(__name__)


async def _still_used(session: AsyncSession, image_id: str) -> bool:
    pattern = f"%/media/{image_id}-%"  # the id is 32 hex characters, so it holds no LIKE wildcards
    checks = (
        select(GalleryItem.id).where(GalleryItem.image_url.like(pattern)).limit(1),
        select(Service.id).where(Service.image_url.like(pattern)).limit(1),
        select(Testimonial.id).where(Testimonial.photo_url.like(pattern)).limit(1),
        select(EnquiryImage.id).where(EnquiryImage.image_id == image_id).limit(1),
    )
    for check in checks:
        if await session.scalar(check) is not None:
            return True
    return False


async def release_image(session: AsyncSession, url: str | None) -> None:
    """Delete the files behind `url` if it is one of our stored pictures and nothing else uses it.
    Never raises: a problem here is logged, because the change the visitor asked for has already succeeded."""
    image_id = image_id_from_url(url)
    if image_id is None:
        return  # no picture, or one hosted somewhere else: not ours to delete
    try:
        if await _still_used(session, image_id):
            return
        await run_in_threadpool(get_storage().delete_image, image_id)
    except Exception as exc:  # noqa: BLE001 - a leftover file is a nuisance; failing the request would be worse
        logger.warning("Could not remove unused image files (%s)", type(exc).__name__)
