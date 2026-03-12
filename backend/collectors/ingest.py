"""Market ingestion service — runs collectors and persists to database."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
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

BATCH_SIZE = 500


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
    """Bulk upsert markets using PostgreSQL INSERT ... ON CONFLICT.

    Processes in batches for memory efficiency.
    """
    if not markets:
        return 0

    # Deduplicate by (platform, platform_id) — keep last occurrence
    seen: dict[tuple[str, str], MarketData] = {}
    for m in markets:
        seen[(m.platform, m.platform_id)] = m
    markets = list(seen.values())

    now = datetime.now(UTC)
    total = 0

    for i in range(0, len(markets), BATCH_SIZE):
        batch = markets[i : i + BATCH_SIZE]
        rows = [
            {
                "id": uuid.uuid4(),
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
                "close_time": m.close_time,
                "last_updated": now,
                "source_url": m.source_url,
                "raw_data": m.raw_data,
                "active": True,
            }
            for m in batch
        ]

        stmt = insert(NormalizedMarket).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_platform_market",
            set_={
                "title": stmt.excluded.title,
                "slug": stmt.excluded.slug,
                "category": stmt.excluded.category,
                "yes_price": stmt.excluded.yes_price,
                "no_price": stmt.excluded.no_price,
                "yes_ask": stmt.excluded.yes_ask,
                "yes_bid": stmt.excluded.yes_bid,
                "no_ask": stmt.excluded.no_ask,
                "no_bid": stmt.excluded.no_bid,
                "volume_24h": stmt.excluded.volume_24h,
                "liquidity": stmt.excluded.liquidity,
                "open_interest": stmt.excluded.open_interest,
                "close_time": stmt.excluded.close_time,
                "last_updated": stmt.excluded.last_updated,
                "source_url": stmt.excluded.source_url,
                "raw_data": stmt.excluded.raw_data,
                "active": stmt.excluded.active,
            },
        )
        await session.execute(stmt)
        total += len(batch)

    return total
