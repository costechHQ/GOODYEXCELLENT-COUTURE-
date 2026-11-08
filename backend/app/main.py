from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.limits import BodyLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.routers import (
    admin,
    admin_enquiries,
    admin_gallery,
    admin_password_reset,
    admin_services,
    admin_settings,
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


def create_app(environment: str | None = None) -> FastAPI:
    """Build the application. `environment` is a parameter so the production settings can be tested."""
    production = (environment or settings.environment) == "production"

    # In production the interactive docs and the schema are switched off: they hand an attacker a
    # complete map of every route. They stay on while developing.
    app = FastAPI(
        title=settings.app_name,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )

    # The last middleware added is the outermost one. Order, inside to out: the body-size guard, then
    # CORS (so the guard's 413 still carries CORS headers), then the security headers (so every
    # response, including CORS preflights and refusals, carries them).
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(SecurityHeadersMiddleware, production=production)

    for router in (
        health.router,
        site_settings.router,
        services.router,
        gallery.router,
        testimonials.router,
        enquiries.router,
        admin.router,
        admin_password_reset.router,
        admin_gallery.router,
        admin_services.router,
        admin_settings.router,
        admin_enquiries.router,
        admin_testimonials.router,
        admin_uploads.router,
        media.router,
    ):
        app.include_router(router)
    return app


app = create_app()
