from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core.storage import get_storage

router = APIRouter(tags=["media"])


@router.get("/media/{name}")
async def get_media(name: str):
    path = get_storage().path_for(name)  # None for anything that is not one of our generated names
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")
    return FileResponse(
        path,
        media_type="image/webp",
        headers={
            # The name is random and never reused, so the file can be cached for good (NFR-04).
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
