from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session

app = FastAPI(title=settings.app_name)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database unavailable") from None
    return {"status": "ok"}
