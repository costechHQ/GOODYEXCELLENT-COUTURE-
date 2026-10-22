"""Idempotent seed: services (FR-19), site settings (SRS 2.5) and the first Owner (FR-51).

Run with: uv run python -m app.db.seed

Service descriptions are neutral placeholders. Replace them with the approved brand copy
(FR-21) through the admin area once it exists. No prices or delivery claims (CR-02).
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AdminUser, Service, SiteSettings
from app.models.enums import AdminRole

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


async def seed(session: AsyncSession) -> None:
    existing = set(await session.scalars(select(Service.slug)))
    for order, (title, slug) in enumerate(SERVICES):
        if slug not in existing:
            session.add(
                Service(
                    title=title,
                    slug=slug,
                    description=f"{title} by GOODYEXCELLENT COUTURE. Description to be supplied.",
                    display_order=order,
                )
            )

    if await session.get(SiteSettings, 1) is None:
        session.add(SiteSettings(id=1))  # column defaults carry the exact contact details

    if settings.admin_email and settings.admin_password:
        found = await session.scalar(
            select(AdminUser).where(AdminUser.email == settings.admin_email)
        )
        if found is None:
            session.add(
                AdminUser(
                    name=settings.admin_name,
                    email=settings.admin_email,
                    hashed_password=hash_password(settings.admin_password),
                    role=AdminRole.owner,
                )
            )

    await session.commit()


async def main() -> None:
    async with SessionLocal() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
