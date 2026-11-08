"""Where uploaded files live. Routes only use these functions, so moving to cloud storage later
means changing this file and nothing else (TS-05)."""

import os
import re
from pathlib import Path

from app.core.config import settings

# Only names we generate ourselves are ever read or written: 32 hex characters, a width, ".webp".
# That makes path tricks such as "../" impossible by construction.
_NAME = re.compile(r"[0-9a-f]{32}-\d{2,4}\.webp")


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


def get_storage() -> LocalStorage:
    # Looked up on every call so the folder can be changed by configuration (and in tests).
    return LocalStorage(Path(settings.upload_dir))


def public_url(name: str) -> str:
    """The absolute address a browser uses to fetch the file (gallery items need absolute URLs)."""
    return f"{settings.api_public_url.rstrip('/')}/media/{name}"
