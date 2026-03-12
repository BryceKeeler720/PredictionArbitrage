"""APScheduler-based job scheduler that orchestrates the full pipeline.

Pipeline per cycle:
1. Run collectors → upsert markets to DB
2. Run matcher on cross-platform markets
3. Run arb engine on matched pairs
4. Send Discord alerts for new opportunities
5. Persist opportunities to DB
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import String, and_, exists, func, select, update

from backend.alerts.discord import send_alert
from backend.collectors.ingest import run_collection_cycle
from backend.config import settings
from backend.db import async_session
from backend.engine.arbitrage import MarketPrices, detect_arbitrage
from backend.matching.matcher import MarketInfo, find_matches
from backend.models.market import MarketMatch, MarketMatchMember, NormalizedMarket
from backend.models.opportunity import ArbitrageOpportunity

logger = logging.getLogger(__name__)


async def run_full_cycle() -> dict:
    """Run the full collection → match → detect → alert pipeline."""
    stats: dict = {"timestamp": datetime.now(UTC).isoformat()}

    # Step 1: Collect markets
    logger.info("=== Starting collection cycle ===")
    try:
        collection_stats = await run_collection_cycle()
        stats["collected"] = collection_stats
        logger.info("Collection done: %s", collection_stats)
    except Exception:
        logger.exception("Collection cycle failed")
        stats["collected"] = {}

    # Step 2: Match markets across platforms
    logger.info("=== Starting matching cycle ===")
    try:
        match_stats = await run_matching_cycle()
        stats["matched"] = match_stats
        logger.info("Matching done: %d new matches", match_stats.get("new_matches", 0))
    except Exception:
        logger.exception("Matching cycle failed")
        stats["matched"] = {}

    # Step 3: Detect arbitrage
    logger.info("=== Starting arb detection ===")
    try:
        arb_stats = await run_arb_detection()
        stats["arbitrage"] = arb_stats
        logger.info("Arb detection done: %d opportunities", arb_stats.get("opportunities", 0))
    except Exception:
        logger.exception("Arb detection failed")
        stats["arbitrage"] = {}

    return stats


async def run_matching_cycle() -> dict:
    """Run the matcher on all active markets from different platforms.

    Only loads markets that exist on at least 2 platforms and have some volume,
    to keep the TF-IDF matrix manageable.
    """
    async with async_session() as session:
        # Get platforms that have markets
        platform_counts = await session.execute(
            select(NormalizedMarket.platform, func.count())
            .where(NormalizedMarket.active.is_(True))
            .group_by(NormalizedMarket.platform)
        )
        platforms = {row[0]: row[1] for row in platform_counts}
        logger.info("Matching: platforms with data: %s", platforms)

        if len(platforms) < 2:
            logger.info("Matching: need at least 2 platforms, skipping")
            return {"total_markets": 0, "new_matches": 0, "platforms": len(platforms)}

        # Load markets from non-Polymarket platforms (smaller sets) fully,
        # and a sample from Polymarket to keep TF-IDF matrix manageable
        all_markets: list[NormalizedMarket] = []
        for platform in platforms:
            query = (
                select(NormalizedMarket)
                .where(NormalizedMarket.active.is_(True))
                .where(NormalizedMarket.platform == platform)
                .where(NormalizedMarket.yes_price > 0.01)
                .where(NormalizedMarket.yes_price < 0.99)
            )
            # For very large platforms, take only higher-volume markets
            if platforms[platform] > 5000:
                query = query.where(NormalizedMarket.volume_24h > 100).limit(5000)
            result = await session.execute(query)
            platform_markets = result.scalars().all()
            all_markets.extend(platform_markets)
            logger.info("Matching: loaded %d markets from %s", len(platform_markets), platform)

    if len(all_markets) < 2:
        return {"total_markets": 0, "new_matches": 0}

    # Convert to MarketInfo for the matcher
    market_infos = [
        MarketInfo(
            platform=m.platform,
            platform_id=m.platform_id,
            title=m.title,
            category=m.category,
            close_time=m.close_time,
        )
        for m in all_markets
    ]

    # Find matches
    candidates = find_matches(
        market_infos,
        confidence_threshold=settings.match_confidence_threshold,
    )

    # Persist new matches (with proper dedup)
    new_count = 0
    skipped = 0
    async with async_session() as session:
        for candidate in candidates:
            # Look up market UUIDs first
            mkt_a_result = await session.execute(
                select(NormalizedMarket.id).where(
                    NormalizedMarket.platform == candidate.market_a_platform,
                    NormalizedMarket.platform_id == candidate.market_a_id,
                )
            )
            mkt_a_uuid = mkt_a_result.scalar_one_or_none()

            mkt_b_result = await session.execute(
                select(NormalizedMarket.id).where(
                    NormalizedMarket.platform == candidate.market_b_platform,
                    NormalizedMarket.platform_id == candidate.market_b_id,
                )
            )
            mkt_b_uuid = mkt_b_result.scalar_one_or_none()

            if not mkt_a_uuid or not mkt_b_uuid:
                continue

            # Dedup: check if these two markets are already in a match together
            alias_a = MarketMatchMember.__table__.alias("ma")
            alias_b = MarketMatchMember.__table__.alias("mb")
            existing = await session.execute(
                select(alias_a.c.match_id).where(
                    and_(
                        alias_a.c.market_id == mkt_a_uuid,
                        alias_b.c.market_id == mkt_b_uuid,
                        alias_a.c.match_id == alias_b.c.match_id,
                    )
                )
            )
            if existing.first():
                skipped += 1
                continue

            # Create new match
            match = MarketMatch(
                canonical_question=candidate.market_a_title,
                match_confidence=candidate.confidence,
                match_method="auto_fuzzy",
                verified=candidate.confidence >= settings.auto_verify_threshold,
            )
            session.add(match)
            await session.flush()

            session.add(MarketMatchMember(match_id=match.id, market_id=mkt_a_uuid))
            session.add(MarketMatchMember(match_id=match.id, market_id=mkt_b_uuid))
            new_count += 1

        await session.commit()

    logger.info("Matching: %d new, %d skipped (already matched)", new_count, skipped)
    return {
        "total_markets": len(all_markets),
        "new_matches": new_count,
        "skipped": skipped,
    }


async def run_arb_detection() -> dict:
    """Detect arbitrage across all matched market pairs."""
    opportunities_found = 0
    alerts_sent = 0

    # Expire stale opportunities that involve play-money platforms
    async with async_session() as session:
        stale = await session.execute(
            select(ArbitrageOpportunity.id)
            .where(ArbitrageOpportunity.status == "active")
            .where(ArbitrageOpportunity.legs.cast(String).contains("manifold"))
        )
        stale_ids = [row[0] for row in stale]
        if stale_ids:
            await session.execute(
                update(ArbitrageOpportunity)
                .where(ArbitrageOpportunity.id.in_(stale_ids))
                .values(status="expired", expired_at=datetime.now(UTC))
            )
            await session.commit()
            logger.info("Expired %d stale manifold opportunities", len(stale_ids))

    async with async_session() as session:
        # Get all active matches with their markets
        matches_result = await session.execute(select(MarketMatch))
        matches = matches_result.scalars().all()

        for match in matches:
            # Get member markets
            members_result = await session.execute(
                select(NormalizedMarket)
                .join(MarketMatchMember, MarketMatchMember.market_id == NormalizedMarket.id)
                .where(MarketMatchMember.match_id == match.id)
                .where(NormalizedMarket.active.is_(True))
            )
            member_markets = members_result.scalars().all()

            if len(member_markets) < 2:
                continue

            # Filter out Manifold (play money — not comparable to real-money platforms)
            real_money_markets = [m for m in member_markets if m.platform != "manifold"]
            if len(real_money_markets) < 2:
                continue

            # Convert to price objects
            prices = [
                MarketPrices(
                    platform=m.platform,
                    platform_id=m.platform_id,
                    title=m.title,
                    yes_ask=m.yes_ask,
                    yes_bid=m.yes_bid,
                    no_ask=m.no_ask,
                    no_bid=m.no_bid,
                    yes_price=m.yes_price,
                    no_price=m.no_price,
                    liquidity=m.liquidity,
                    source_url=m.source_url or "",
                )
                for m in real_money_markets
            ]

            # Detect arbs
            opps = detect_arbitrage(
                match_id=str(match.id),
                question=match.canonical_question,
                markets=prices,
                min_profit_pct=settings.min_profit_pct,
                min_liquidity_usd=settings.min_liquidity_usd,
            )

            for opp in opps:
                # Check if same match already has an active opportunity
                existing_opp = await session.execute(
                    select(exists().where(
                        and_(
                            ArbitrageOpportunity.match_id == match.id,
                            ArbitrageOpportunity.status == "active",
                        )
                    ))
                )
                if existing_opp.scalar():
                    continue

                opportunities_found += 1

                # Persist to DB
                db_opp = ArbitrageOpportunity(
                    match_id=match.id,
                    type=opp.type,
                    legs=[
                        {
                            "platform": leg.platform,
                            "market_id": leg.market_id,
                            "side": leg.side,
                            "price": leg.price,
                            "fee_rate": leg.fee_rate,
                            "effective_cost": leg.effective_cost,
                            "available_size_usd": leg.available_size_usd,
                            "cost_fraction": leg.cost_fraction,
                            "source_url": leg.source_url,
                        }
                        for leg in opp.legs
                    ],
                    total_cost=opp.total_cost,
                    guaranteed_profit=opp.guaranteed_profit,
                    profit_after_fees=opp.profit_after_fees,
                    profit_pct=opp.profit_pct,
                    max_size_usd=opp.max_size_usd,
                    description=opp.question[:500],
                )
                session.add(db_opp)

                # Send Discord alert
                sent = await send_alert(opp)
                if sent:
                    alerts_sent += 1

        await session.commit()

    return {"opportunities": opportunities_found, "alerts_sent": alerts_sent}


def setup_scheduler(app) -> None:
    """Set up APScheduler jobs on the FastAPI app."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_full_cycle,
        "interval",
        seconds=settings.poll_interval_seconds,
        id="full_cycle",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started — polling every %ds", settings.poll_interval_seconds)

    # Store ref so it doesn't get GC'd
    app.state.scheduler = scheduler
