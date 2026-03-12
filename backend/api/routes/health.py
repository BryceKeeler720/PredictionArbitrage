import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_session

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict:
    checks: dict = {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}

    # Database check
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        checks["status"] = "degraded"

    # Collector reachability (lightweight)
    for name, url in [
        ("polymarket", "https://gamma-api.polymarket.com/markets?limit=1"),
        ("kalshi", "https://api.elections.kalshi.com/trade-api/v2/markets?limit=1"),
        ("manifold", "https://api.manifold.markets/v0/markets?limit=1"),
    ]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                checks[name] = "ok" if resp.status_code == 200 else f"status {resp.status_code}"
        except Exception as e:
            checks[name] = f"error: {e}"

    return checks
