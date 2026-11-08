"""Puts the starting data in the database. Safe to run any number of times.

Run with: uv run python -m app.db.seed
"""

import asyncio

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import MIN_PASSWORD_LENGTH, hash_password
from app.db.session import SessionLocal
from app.models import AdminUser, Service, SiteSettings
from app.models.enums import AdminRole

MIN_OWNER_PASSWORD_LENGTH = MIN_PASSWORD_LENGTH  # NFR-06

# The eight services in FR-19, in display order.
SERVICES = [
    ("Senator Wear", "senator-wear"),
    ("Kaftans", "kaftans"),
    ("Suits and Formal Wear", "suits-and-formal-wear"),
    ("Shirts", "shirts"),
    ("Trousers", "trousers"),
    ("Agbada and Chieftaincy Wears", "agbada-and-chieftaincy-wears"),
    ("Women's Senator Wear", "womens-senator-wear"),
    ("Fashion Consultations", "fashion-consultations"),
]


async def seed_owner(session: AsyncSession) -> None:
    """Create the first Owner from OWNER_EMAIL and OWNER_PASSWORD (FR-51, FR-57).

    Does nothing if the variables are not set or an Owner already exists, so it never overwrites
    or adds accounts. Stops with an error if the values are set but unusable.
    """
    email, password = settings.owner_email.strip(), settings.owner_password.get_secret_value()
    if not email and not password:
        return
    if not email or not password:
        raise SystemExit("Set both OWNER_EMAIL and OWNER_PASSWORD, or neither.")
    try:
        email = str(TypeAdapter(EmailStr).validate_python(email))
    except ValidationError:
        raise SystemExit("OWNER_EMAIL is not a valid email address.") from None
    if len(password) < MIN_OWNER_PASSWORD_LENGTH:
        raise SystemExit(f"OWNER_PASSWORD must be at least {MIN_OWNER_PASSWORD_LENGTH} characters.")

    if await session.scalar(select(AdminUser.id).where(AdminUser.role == AdminRole.owner).limit(1)) is not None:
        return
    session.add(AdminUser(email=email, password_hash=hash_password(password), role=AdminRole.owner))


async def seed(session: AsyncSession) -> None:
    # site_settings is a single-row table; the model defaults carry the exact
    # contact details from SRS 2.5, so an empty SiteSettings() is enough.
    if await session.get(SiteSettings, 1) is None:
        session.add(SiteSettings(id=1))

    # Add only the services that are missing, matched by slug, so edits are never overwritten.
    existing = set(await session.scalars(select(Service.slug)))
    for order, (title, slug) in enumerate(SERVICES):
        if slug not in existing:
            session.add(
                Service(
                    title=title,
                    slug=slug,
                    # Placeholder: replace with the approved brand copy (FR-21). No prices or
                    # delivery claims until the owner confirms them (CR-02).
                    description="Description to be supplied.",
                    display_order=order,
                )
            )

    await seed_owner(session)

    await session.commit()


async def main() -> None:
    async with SessionLocal() as session:
        await seed(session)
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
