"""Manifold Markets collector — public API, no auth required.

Manifold is play-money but useful as a price signal and for cross-referencing
with real-money platforms. 0% fees. Rate limit: 500 req/min.
"""

import contextlib
import logging
from datetime import UTC, datetime

from backend.collectors.base import BaseCollector, MarketData

logger = logging.getLogger(__name__)

MANIFOLD_API = "https://api.manifold.markets/v0"


class ManifoldCollector(BaseCollector):
    platform_name = "manifold"
    base_url = MANIFOLD_API

    async def fetch_markets(self) -> list[MarketData]:
        """Fetch active binary markets from Manifold."""
        markets: list[MarketData] = []
        before: str | None = None
        page_size = 1000

        try:
            while True:
                params: dict[str, str | int] = {"limit": page_size}
                if before:
                    params["before"] = before

                data = await self._get(f"{MANIFOLD_API}/markets", params=params)
                if not isinstance(data, list) or len(data) == 0:
                    break

                for raw in data:
                    m = self._parse_market(raw)
                    if m:
                        markets.append(m)

                # Paginate using the last market's ID
                before = data[-1].get("id", "")
                if len(data) < page_size:
                    break

        except Exception:
            logger.exception("Manifold fetch failed")

        logger.info("Manifold: fetched %d markets", len(markets))
        return markets

    async def fetch_prices(self, market_ids: list[str]) -> dict[str, MarketData]:
        """Fetch individual markets by slug/ID."""
        results: dict[str, MarketData] = {}
        for mid in market_ids:
            try:
                raw = await self._get(f"{MANIFOLD_API}/market/{mid}")
                if isinstance(raw, dict):
                    m = self._parse_market(raw)
                    if m:
                        results[m.platform_id] = m
            except Exception:
                logger.warning("Failed to fetch Manifold market %s", mid)
        return results

    def _parse_market(self, raw: dict) -> MarketData | None:
        """Parse a Manifold market JSON into MarketData."""
        # Only binary markets have yes/no prices
        outcome_type = raw.get("outcomeType", "")
        if outcome_type != "BINARY":
            return None

        # Skip resolved or closed markets
        if raw.get("isResolved", False):
            return None

        market_id = raw.get("id", "")
        title = raw.get("question", "")
        if not market_id or not title:
            return None

        prob = raw.get("probability", 0.0)
        yes_price = round(prob, 4)
        no_price = round(1.0 - prob, 4)

        slug = raw.get("slug", "")
        source_url = f"https://manifold.markets/{raw.get('creatorUsername', '')}/{slug}"

        # Volume (Manifold reports total volume in mana)
        volume = raw.get("volume24Hours", 0.0)
        liquidity = raw.get("totalLiquidity", 0.0)

        # Close time
        close_time = None
        close_ts = raw.get("closeTime")
        if close_ts:
            with contextlib.suppress(Exception):
                close_time = datetime.fromtimestamp(close_ts / 1000, tz=UTC)

        # Category from group slugs or default
        group_slugs = raw.get("groupSlugs", [])
        category = group_slugs[0] if group_slugs else "unknown"

        return MarketData(
            platform="manifold",
            platform_id=market_id,
            title=title,
            slug=slug,
            category=category,
            yes_price=yes_price,
            no_price=no_price,
            volume_24h=volume,
            liquidity=liquidity,
            close_time=close_time,
            source_url=source_url,
            raw_data=raw,
        )
