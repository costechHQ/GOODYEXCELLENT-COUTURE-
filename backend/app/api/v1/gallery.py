"""Public gallery with category filter and admin upload (FR-24 to FR-29)."""

from fastapi import APIRouter

router = APIRouter(prefix="/gallery", tags=["gallery"])
