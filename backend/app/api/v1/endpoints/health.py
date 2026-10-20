from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.services.exceptions import ServiceUnavailableError

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def liveness():
    return {"status": "ok"}


@router.get("/ready")
async def readiness():
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        raise ServiceUnavailableError("Database unavailable")
    return {"status": "ok", "database": "ok"}