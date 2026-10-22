"""Enquiry submission and admin management (FR-30 to FR-38, FR-42, FR-47, FR-53, FR-54, FR-58)."""

from fastapi import APIRouter

router = APIRouter(prefix="/enquiries", tags=["enquiries"])
