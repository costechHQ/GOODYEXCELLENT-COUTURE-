from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import admin, admin_gallery, admin_services, enquiries, gallery, health, services, testimonials
from app.routers import settings as site_settings

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(site_settings.router)
app.include_router(services.router)
app.include_router(gallery.router)
app.include_router(testimonials.router)
app.include_router(enquiries.router)
app.include_router(admin.router)
app.include_router(admin_gallery.router)
app.include_router(admin_services.router)
