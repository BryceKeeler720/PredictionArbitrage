from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_session
from backend.models.opportunity import ArbitrageOpportunity

router = APIRouter()


@router.get("/opportunities")
async def list_opportunities(
    status: str = "active",
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    query = (
        select(ArbitrageOpportunity)
        .where(ArbitrageOpportunity.status == status)
        .order_by(ArbitrageOpportunity.profit_pct.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)
    opps = result.scalars().all()

    return {
        "opportunities": [
            {
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
            }
            for o in opps
        ],
        "limit": limit,
        "offset": offset,
    }
