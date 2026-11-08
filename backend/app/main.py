from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.limits import BodyLimitMiddleware
from app.routers import (
    admin,
    admin_enquiries,
    admin_gallery,
    admin_password_reset,
    admin_services,
    admin_testimonials,
    admin_uploads,
    enquiries,
    gallery,
    health,
    media,
    services,
    testimonials,
)
from app.routers import settings as site_settings

app = FastAPI(title=settings.app_name)

# Added first, so CORS (added after, and therefore outside it) still decorates its 413 answers.
app.add_middleware(BodyLimitMiddleware)
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
app.include_router(admin_password_reset.router)
app.include_router(admin_gallery.router)
app.include_router(admin_services.router)
app.include_router(admin_enquiries.router)
app.include_router(admin_testimonials.router)
app.include_router(admin_uploads.router)
app.include_router(media.router)
