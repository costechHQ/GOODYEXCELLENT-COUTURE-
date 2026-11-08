"""Where uploaded files live. Routes only use these functions, so moving to cloud storage later
means changing this file and nothing else (TS-05)."""

import os
import re
from pathlib import Path

from app.core.config import settings

# Only names we generate ourselves are ever read or written: 32 hex characters, a width, ".webp".
# That makes path tricks such as "../" impossible by construction.
_NAME = re.compile(r"[0-9a-f]{32}-\d{2,4}\.webp")
_IMAGE_ID = re.compile(r"[0-9a-f]{32}")


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def save(self, name: str, data: bytes) -> None:
        if not _NAME.fullmatch(name):
            raise ValueError("unsafe file name")
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.root / f"{name}.part"
        temporary.write_bytes(data)
        os.replace(temporary, self.root / name)  # a half-written file is never served

    def path_for(self, name: str) -> Path | None:
        """The file's location, or None if the name is not one of ours or the file is missing."""
        if not _NAME.fullmatch(name):
            return None
        path = self.root / name
        return path if path.is_file() else None

    def delete(self, name: str) -> None:
        path = self.path_for(name)
        if path is not None:
            path.unlink(missing_ok=True)

    def delete_image(self, image_id: str) -> int:
        """Remove every stored size of one image. Returns how many files were deleted."""
        if not _IMAGE_ID.fullmatch(image_id) or not self.root.is_dir():
            return 0
        removed = 0
        for path in self.root.glob(f"{image_id}-*.webp"):
            if _NAME.fullmatch(path.name):  # belt and braces: only files that look exactly like ours
                path.unlink(missing_ok=True)
                removed += 1
        return removed


def get_storage() -> LocalStorage:
    # Looked up on every call so the folder can be changed by configuration (and in tests).
    return LocalStorage(Path(settings.upload_dir))


def _media_prefix() -> str:
    return f"{settings.api_public_url.rstrip('/')}/media/"


def public_url(name: str) -> str:
    """The absolute address a browser uses to fetch the file (gallery items need absolute URLs)."""
    return f"{_media_prefix()}{name}"


def image_id_from_url(url: str | None) -> str | None:
    """The id of one of OUR stored images, or None for anything else.

    A URL counts only if it starts with this API's own /media/ address and ends in a name of exactly
    the shape we generate. A picture hosted elsewhere, or a URL that merely imitates our path on
    another host, gives None, so it can never cause one of our files to be deleted."""
    if not url or not url.startswith(_media_prefix()):
        return None
    name = url[len(_media_prefix()) :]
    return name[:32] if _NAME.fullmatch(name) else None
