"""Puts the starting data in the database. Safe to run any number of times.

Run with: uv run python -m app.db.seed
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models import SiteSettings


async def seed(session: AsyncSession) -> None:
    # site_settings is a single-row table; the model defaults carry the exact
    # contact details from SRS 2.5, so an empty SiteSettings() is enough.
    if await session.get(SiteSettings, 1) is None:
        session.add(SiteSettings(id=1))
    await session.commit()


async def main() -> None:
    async with SessionLocal() as session:
        await seed(session)
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
