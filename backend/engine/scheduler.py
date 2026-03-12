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

from sqlalchemy import select

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
    collection_stats = await run_collection_cycle()
    stats["collected"] = collection_stats
    logger.info("Collection done: %s", collection_stats)

    # Step 2: Match markets across platforms
    logger.info("=== Starting matching cycle ===")
    match_stats = await run_matching_cycle()
    stats["matched"] = match_stats
    logger.info("Matching done: %d new matches", match_stats.get("new_matches", 0))

    # Step 3: Detect arbitrage
    logger.info("=== Starting arb detection ===")
    arb_stats = await run_arb_detection()
    stats["arbitrage"] = arb_stats
    logger.info("Arb detection done: %d opportunities", arb_stats.get("opportunities", 0))

    return stats


async def run_matching_cycle() -> dict:
    """Run the matcher on all active markets from different platforms."""
    async with async_session() as session:
        result = await session.execute(
            select(NormalizedMarket)
            .where(NormalizedMarket.active.is_(True))
            .where(NormalizedMarket.volume_24h > settings.min_volume_24h)
        )
        db_markets = result.scalars().all()

    if not db_markets:
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
        for m in db_markets
    ]

    # Find matches
    candidates = find_matches(
        market_infos,
        confidence_threshold=settings.match_confidence_threshold,
    )

    # Persist new matches
    new_count = 0
    async with async_session() as session:
        for candidate in candidates:
            # Check if this pair already exists
            await session.execute(
                select(MarketMatchMember)
                .join(
                    MarketMatchMember,
                    MarketMatchMember.match_id == MarketMatch.id,
                    isouter=True,
                )
                .where(MarketMatchMember.market_id.in_([
                    # Look up market UUIDs
                ]))
            )
            # For simplicity, deduplicate by checking if a match with these
            # two platform+id combos already exists
            # TODO: proper dedup query
            match = MarketMatch(
                canonical_question=candidate.market_a_title,
                match_confidence=candidate.confidence,
                match_method="auto_fuzzy",
                verified=candidate.confidence >= settings.auto_verify_threshold,
            )
            session.add(match)
            await session.flush()

            # Look up market UUIDs
            for pid, pplat in [
                (candidate.market_a_id, candidate.market_a_platform),
                (candidate.market_b_id, candidate.market_b_platform),
            ]:
                mkt_result = await session.execute(
                    select(NormalizedMarket.id).where(
                        NormalizedMarket.platform == pplat,
                        NormalizedMarket.platform_id == pid,
                    )
                )
                mkt_uuid = mkt_result.scalar_one_or_none()
                if mkt_uuid:
                    session.add(MarketMatchMember(match_id=match.id, market_id=mkt_uuid))

            new_count += 1

        await session.commit()

    return {"total_markets": len(db_markets), "new_matches": new_count}


async def run_arb_detection() -> dict:
    """Detect arbitrage across all matched market pairs."""
    opportunities_found = 0
    alerts_sent = 0

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
                    liquidity=m.liquidity,
                )
                for m in member_markets
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
