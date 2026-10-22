"""Admin sign-in, password reset (FR-51, FR-56, NFR-06)."""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])
