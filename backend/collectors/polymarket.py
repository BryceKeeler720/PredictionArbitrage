"""Polymarket collector using Gamma API for discovery and CLOB API for pricing."""

import contextlib
import logging
from datetime import datetime

from backend.collectors.base import BaseCollector, MarketData

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"


class PolymarketCollector(BaseCollector):
    platform_name = "polymarket"
    base_url = GAMMA_BASE

    async def fetch_markets(self) -> list[MarketData]:
        """Fetch active binary markets from the Gamma API with pagination."""
        all_markets: list[MarketData] = []
        offset = 0
        limit = 100

        while True:
            params = {
                "closed": "false",
                "active": "true",
                "limit": limit,
                "offset": offset,
            }
            try:
                data = await self._get(f"{GAMMA_BASE}/markets", params=params)
            except Exception:
                logger.exception("Polymarket Gamma fetch failed at offset %d", offset)
                break

            if not data:
                break

            for raw in data:
                market = self._parse_gamma_market(raw)
                if market:
                    all_markets.append(market)

            if len(data) < limit:
                break
            offset += limit

        logger.info("Polymarket: fetched %d markets", len(all_markets))
        return all_markets

    async def fetch_prices(self, market_ids: list[str]) -> dict[str, MarketData]:
        """Fetch CLOB orderbook prices for specific token IDs.

        market_ids should be Polymarket condition IDs. We look up token IDs
        from the cached raw_data, then hit the CLOB for live pricing.
        """
        results: dict[str, MarketData] = {}

        for market_id in market_ids:
            try:
                # Fetch the Gamma market to get token IDs
                data = await self._get(f"{GAMMA_BASE}/markets/{market_id}")
                if not data:
                    continue

                market = self._parse_gamma_market(data)
                if not market:
                    continue

                # Try to get CLOB prices via token IDs
                tokens = data.get("clobTokenIds")
                if tokens and isinstance(tokens, str):
                    # clobTokenIds is a JSON string like "[\"id1\",\"id2\"]"
                    import json

                    try:
                        tokens = json.loads(tokens)
                    except (json.JSONDecodeError, TypeError):
                        tokens = None

                if tokens and len(tokens) >= 1:
                    market = await self._enrich_with_clob(market, tokens)

                results[market_id] = market
            except Exception:
                logger.exception("Polymarket price fetch failed for %s", market_id)

        return results

    async def _enrich_with_clob(
        self, market: MarketData, token_ids: list[str]
    ) -> MarketData:
        """Fetch CLOB orderbook for YES/NO tokens and update market prices."""
        try:
            # Token 0 = YES, Token 1 = NO (Polymarket convention)
            yes_token = token_ids[0]
            book = await self._get(f"{CLOB_BASE}/book", params={"token_id": yes_token})

            if book:
                bids = book.get("bids", [])
                asks = book.get("asks", [])

                if bids:
                    market.yes_bid = float(bids[0].get("price", 0))
                if asks:
                    market.yes_ask = float(asks[0].get("price", 0))

                # Derive NO from YES
                if market.yes_ask is not None:
                    market.no_bid = round(1.0 - market.yes_ask, 4)
                if market.yes_bid is not None:
                    market.no_ask = round(1.0 - market.yes_bid, 4)

                # Estimate liquidity from top-of-book size
                if bids:
                    market.liquidity = float(bids[0].get("size", 0))
        except Exception:
            logger.exception("CLOB enrichment failed for token %s", token_ids[0])

        return market

    def _parse_gamma_market(self, raw: dict) -> MarketData | None:
        """Parse a Gamma API market response into MarketData."""
        # Skip non-binary markets
        market_type = raw.get("marketType", "")
        if market_type and market_type != "binary":
            return None

        condition_id = raw.get("conditionId") or raw.get("id")
        if not condition_id:
            return None

        title = raw.get("question", "") or raw.get("title", "")
        if not title:
            return None

        # Parse prices
        yes_price = self._safe_float(raw.get("outcomePrices", ""))
        no_price = 0.0
        if isinstance(raw.get("outcomePrices"), str):
            import json

            try:
                prices = json.loads(raw["outcomePrices"])
                if len(prices) >= 2:
                    yes_price = float(prices[0])
                    no_price = float(prices[1])
            except (json.JSONDecodeError, TypeError, ValueError, IndexError):
                pass

        if yes_price == 0.0:
            yes_price = self._safe_float(raw.get("bestAsk", 0))
        if yes_price > 0 and no_price == 0.0:
            no_price = round(1.0 - yes_price, 4)

        # Parse close time
        close_time = None
        end_date = raw.get("endDate") or raw.get("expirationDate")
        if end_date:
            with contextlib.suppress(ValueError, AttributeError):
                close_time = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        slug = raw.get("slug", "") or ""
        volume_24h = self._safe_float(raw.get("volume24hr", 0))
        liquidity = self._safe_float(raw.get("liquidity", 0))

        source_url = f"https://polymarket.com/event/{slug}" if slug else ""

        category = raw.get("category", "unknown") or "unknown"

        return MarketData(
            platform="polymarket",
            platform_id=str(condition_id),
            title=title,
            slug=slug,
            category=category.lower(),
            yes_price=yes_price,
            no_price=no_price,
            volume_24h=volume_24h,
            liquidity=liquidity,
            close_time=close_time,
            source_url=source_url,
            raw_data=raw,
        )

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
