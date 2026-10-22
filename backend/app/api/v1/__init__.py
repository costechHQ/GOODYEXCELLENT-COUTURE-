from fastapi import APIRouter

from app.api.v1 import auth, enquiries, gallery, health, services, site_settings, testimonials

api_router = APIRouter()
for module in (health, auth, enquiries, services, gallery, testimonials, site_settings):
    api_router.include_router(module.router)
