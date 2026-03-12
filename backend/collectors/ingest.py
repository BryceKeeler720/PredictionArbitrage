"""Market ingestion service — runs collectors and persists to database."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.collectors.base import BaseCollector, MarketData
from backend.collectors.kalshi import KalshiCollector
from backend.collectors.manifold import ManifoldCollector
from backend.collectors.polymarket import PolymarketCollector
from backend.collectors.predictit import PredictItCollector
from backend.db import async_session
from backend.models.market import NormalizedMarket

logger = logging.getLogger(__name__)

COLLECTORS: list[type[BaseCollector]] = [
    PolymarketCollector,
    KalshiCollector,
    PredictItCollector,
    ManifoldCollector,
]


async def run_collection_cycle() -> dict[str, int]:
    """Run all collectors and upsert markets into the database.

    Returns a dict of {platform: count} for markets upserted.
    """
    stats: dict[str, int] = {}

    for collector_cls in COLLECTORS:
        collector = collector_cls()
        try:
            markets = await collector.fetch_markets()
            async with async_session() as session:
                count = await _upsert_markets(session, markets)
                await session.commit()
                stats[collector.platform_name] = count
                logger.info("%s: upserted %d markets", collector.platform_name, count)
        except Exception:
            logger.exception("Collection cycle failed for %s", collector.platform_name)
            stats[collector.platform_name] = 0
        finally:
            await collector.close()

    return stats


async def _upsert_markets(session: AsyncSession, markets: list[MarketData]) -> int:
    """Insert or update markets in the database. Returns count of upserted rows."""
    count = 0
    for m in markets:
        result = await session.execute(
            select(NormalizedMarket).where(
                NormalizedMarket.platform == m.platform,
                NormalizedMarket.platform_id == m.platform_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.title = m.title
            existing.slug = m.slug
            existing.category = m.category
            existing.yes_price = m.yes_price
            existing.no_price = m.no_price
            existing.yes_ask = m.yes_ask
            existing.yes_bid = m.yes_bid
            existing.no_ask = m.no_ask
            existing.no_bid = m.no_bid
            existing.volume_24h = m.volume_24h
            existing.liquidity = m.liquidity
            existing.open_interest = m.open_interest
            existing.close_time = m.close_time
            existing.last_updated = datetime.now(UTC)
            existing.source_url = m.source_url
            existing.raw_data = m.raw_data
            existing.active = True
        else:
            session.add(
                NormalizedMarket(
                    platform=m.platform,
                    platform_id=m.platform_id,
                    title=m.title,
                    slug=m.slug,
                    category=m.category,
                    yes_price=m.yes_price,
                    no_price=m.no_price,
                    yes_ask=m.yes_ask,
                    yes_bid=m.yes_bid,
                    no_ask=m.no_ask,
                    no_bid=m.no_bid,
                    volume_24h=m.volume_24h,
                    liquidity=m.liquidity,
                    open_interest=m.open_interest,
                    close_time=m.close_time,
                    last_updated=datetime.now(UTC),
                    source_url=m.source_url,
                    raw_data=m.raw_data,
                    active=True,
                )
            )
        count += 1

    return count
