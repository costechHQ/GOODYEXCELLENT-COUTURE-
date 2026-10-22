"""Puts the starting data in the database. Safe to run any number of times.

Run with: uv run python -m app.db.seed
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models import Service, SiteSettings

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

    await session.commit()


async def main() -> None:
    async with SessionLocal() as session:
        await seed(session)
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
