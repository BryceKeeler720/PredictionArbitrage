from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_session
from backend.models.market import MarketMatch
from backend.models.opportunity import ArbitrageOpportunity

router = APIRouter()


@router.get("/opportunities")
async def list_opportunities(
    status: str = "active",
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    min_profit: float = Query(default=None, description="Min profit %"),
    max_profit: float = Query(default=None, description="Max profit %"),
    platform: str = Query(default=None, description="Filter by platform in any leg"),
    min_liquidity: float = Query(default=None, description="Min max_size_usd"),
    sort: str = Query(default="profit_desc", description="Sort: profit_desc, profit_asc, cost_asc, size_desc, newest"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    query = (
        select(ArbitrageOpportunity)
        .where(ArbitrageOpportunity.status == status)
    )

    # Profit range filters
    if min_profit is not None:
        query = query.where(ArbitrageOpportunity.profit_pct >= min_profit)
    if max_profit is not None:
        query = query.where(ArbitrageOpportunity.profit_pct <= max_profit)

    # Liquidity filter
    if min_liquidity is not None:
        query = query.where(ArbitrageOpportunity.max_size_usd >= min_liquidity)

    # Sort
    sort_map = {
        "profit_desc": ArbitrageOpportunity.profit_pct.desc(),
        "profit_asc": ArbitrageOpportunity.profit_pct.asc(),
        "cost_asc": ArbitrageOpportunity.total_cost.asc(),
        "size_desc": ArbitrageOpportunity.max_size_usd.desc(),
        "newest": ArbitrageOpportunity.detected_at.desc(),
    }
    query = query.order_by(sort_map.get(sort, ArbitrageOpportunity.profit_pct.desc()))
    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    opps = result.scalars().all()

    # Get match confidences for all match_ids in one query
    match_ids = list({o.match_id for o in opps})
    confidence_map: dict = {}
    if match_ids:
        match_result = await session.execute(
            select(MarketMatch.id, MarketMatch.match_confidence)
            .where(MarketMatch.id.in_(match_ids))
        )
        confidence_map = {row[0]: row[1] for row in match_result}

    # Get total count (with same filters)
    count_query = (
        select(func.count())
        .select_from(ArbitrageOpportunity)
        .where(ArbitrageOpportunity.status == status)
    )
    if min_profit is not None:
        count_query = count_query.where(ArbitrageOpportunity.profit_pct >= min_profit)
    if max_profit is not None:
        count_query = count_query.where(ArbitrageOpportunity.profit_pct <= max_profit)
    if min_liquidity is not None:
        count_query = count_query.where(ArbitrageOpportunity.max_size_usd >= min_liquidity)
    total = (await session.execute(count_query)).scalar() or 0

    # Platform filter is applied post-query (legs are JSONB)
    opportunities = []
    for o in opps:
        if platform:
            leg_platforms = [leg.get("platform", "") for leg in (o.legs or [])]
            if platform not in leg_platforms:
                continue

        opportunities.append({
            "id": str(o.id),
            "match_id": str(o.match_id),
            "type": o.type,
            "legs": o.legs,
            "total_cost": o.total_cost,
            "guaranteed_profit": o.guaranteed_profit,
            "profit_after_fees": o.profit_after_fees,
            "profit_pct": o.profit_pct,
            "max_size_usd": o.max_size_usd,
            "status": o.status,
            "detected_at": o.detected_at.isoformat(),
            "description": o.description,
            "match_confidence": confidence_map.get(o.match_id, 0.0),
        })

    return {
        "opportunities": opportunities,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
