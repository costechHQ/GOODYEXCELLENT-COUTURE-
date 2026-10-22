"""Public service listing and admin edits (FR-19 to FR-23, FR-52)."""

from fastapi import APIRouter

router = APIRouter(prefix="/services", tags=["services"])
