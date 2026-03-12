
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_session
from backend.models.market import NormalizedMarket

router = APIRouter()


@router.get("/markets")
async def list_markets(
    platform: str | None = None,
    category: str | None = None,
    active: bool = True,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    query = select(NormalizedMarket).where(NormalizedMarket.active == active)

    if platform:
        query = query.where(NormalizedMarket.platform == platform)
    if category:
        query = query.where(NormalizedMarket.category == category)

    query = query.order_by(NormalizedMarket.volume_24h.desc()).offset(offset).limit(limit)

    count_query = select(func.count()).select_from(
        select(NormalizedMarket.id).where(NormalizedMarket.active == active).subquery()
    )
    if platform:
        count_query = select(func.count()).select_from(
            select(NormalizedMarket.id)
            .where(NormalizedMarket.active == active, NormalizedMarket.platform == platform)
            .subquery()
        )

    result = await session.execute(query)
    markets = result.scalars().all()
    total = (await session.execute(count_query)).scalar() or 0

    return {
        "markets": [_market_to_dict(m) for m in markets],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/markets/{platform}/{platform_id}")
async def get_market(
    platform: str,
    platform_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    query = select(NormalizedMarket).where(
        NormalizedMarket.platform == platform,
        NormalizedMarket.platform_id == platform_id,
    )
    result = await session.execute(query)
    market = result.scalar_one_or_none()
    if not market:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Market not found")
    return _market_to_dict(market)


def _market_to_dict(m: NormalizedMarket) -> dict:
    return {
        "id": str(m.id),
        "platform": m.platform,
        "platform_id": m.platform_id,
        "title": m.title,
        "slug": m.slug,
        "category": m.category,
        "yes_price": m.yes_price,
        "no_price": m.no_price,
        "yes_ask": m.yes_ask,
        "yes_bid": m.yes_bid,
        "no_ask": m.no_ask,
        "no_bid": m.no_bid,
        "volume_24h": m.volume_24h,
        "liquidity": m.liquidity,
        "open_interest": m.open_interest,
        "close_time": m.close_time.isoformat() if m.close_time else None,
        "last_updated": m.last_updated.isoformat(),
        "source_url": m.source_url,
        "active": m.active,
    }
