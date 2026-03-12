"""Kalshi collector using the v2 trade API.

IMPORTANT: Kalshi is removing legacy integer price fields on March 12, 2026.
This collector uses the `_dollars` and `_fp` fields exclusively.
"""

import asyncio
import contextlib
import logging
from datetime import datetime

from backend.collectors.base import BaseCollector, MarketData

logger = logging.getLogger(__name__)

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"


class KalshiCollector(BaseCollector):
    platform_name = "kalshi"
    base_url = KALSHI_BASE

    async def fetch_markets(self) -> list[MarketData]:
        """Fetch all open markets with cursor pagination."""
        all_markets: list[MarketData] = []
        cursor: str | None = None
        limit = 1000

        while True:
            params: dict[str, str | int] = {
                "status": "open",
                "limit": limit,
            }
            if cursor:
                params["cursor"] = cursor

            try:
                data = await self._get(f"{KALSHI_BASE}/markets", params=params)
            except Exception:
                logger.exception("Kalshi market fetch failed at cursor=%s", cursor)
                break

            markets_list = data.get("markets", []) if isinstance(data, dict) else []
            for raw in markets_list:
                market = self._parse_market(raw)
                if market:
                    all_markets.append(market)

            # Cursor pagination
            cursor = data.get("cursor") if isinstance(data, dict) else None
            if not cursor or not markets_list:
                break

            # Respect rate limits
            await asyncio.sleep(0.5)

        logger.info("Kalshi: fetched %d markets", len(all_markets))
        return all_markets

    async def fetch_prices(self, market_ids: list[str]) -> dict[str, MarketData]:
        """Fetch current prices for specific market tickers."""
        results: dict[str, MarketData] = {}

        for ticker in market_ids:
            try:
                data = await self._get(f"{KALSHI_BASE}/markets/{ticker}")
                market_data = data.get("market", data) if isinstance(data, dict) else data
                market = self._parse_market(market_data)
                if market:
                    results[ticker] = market
            except Exception:
                logger.exception("Kalshi price fetch failed for %s", ticker)

        return results

    def _parse_market(self, raw: dict) -> MarketData | None:
        """Parse a Kalshi market response into MarketData.

        Uses `_dollars` fields per the March 2026 field migration.
        """
        ticker = raw.get("ticker", "")
        if not ticker:
            return None

        # Skip multi-leg cross-category parlays — not useful for arb matching
        if "CROSSCATEGORY" in ticker.upper() or "KXMVE" in ticker.upper():
            return None

        title = raw.get("title", "")
        if not title:
            return None

        # Use _dollars fields (float, 0.0-1.0 range) — NOT legacy integer cents
        yes_bid = self._price_dollars(raw, "yes_bid")
        yes_ask = self._price_dollars(raw, "yes_ask")
        no_bid = self._price_dollars(raw, "no_bid")
        no_ask = self._price_dollars(raw, "no_ask")
        last_price = self._price_dollars(raw, "last_price")

        # Midpoint as fallback
        yes_price = last_price
        if yes_ask is not None and yes_bid is not None:
            yes_price = round((yes_ask + yes_bid) / 2, 4)
        elif yes_ask is not None:
            yes_price = yes_ask

        no_price = round(1.0 - yes_price, 4) if yes_price else 0.0

        # Volume and liquidity
        volume_24h = self._safe_float(raw.get("volume_24h", 0))
        volume = self._safe_float(raw.get("volume", 0))
        open_interest = self._safe_float(raw.get("open_interest", 0))
        liquidity = self._safe_float(raw.get("liquidity", 0))

        # Close time
        close_time = None
        expiration = raw.get("expiration_time") or raw.get("close_time")
        if expiration:
            with contextlib.suppress(ValueError, AttributeError):
                close_time = datetime.fromisoformat(expiration.replace("Z", "+00:00"))

        category = raw.get("category", "unknown") or "unknown"

        source_url = f"https://kalshi.com/markets/{ticker}"

        return MarketData(
            platform="kalshi",
            platform_id=ticker,
            title=title,
            slug=ticker.lower(),
            category=category.lower(),
            yes_price=yes_price,
            no_price=no_price,
            yes_ask=yes_ask,
            yes_bid=yes_bid,
            no_ask=no_ask,
            no_bid=no_bid,
            volume_24h=volume_24h if volume_24h else volume,
            liquidity=liquidity,
            open_interest=open_interest,
            close_time=close_time,
            source_url=source_url,
            raw_data=raw,
        )

    def _price_dollars(self, raw: dict, field: str) -> float | None:
        """Extract a price using the _dollars field (0.0-1.0 float).

        Falls back to legacy cents field divided by 100 if _dollars not present.
        """
        # Prefer _dollars field
        dollars_val = raw.get(f"{field}_dollars")
        if dollars_val is not None:
            try:
                return float(dollars_val)
            except (TypeError, ValueError):
                pass

        # Fallback: _fp field (fixed-point)
        fp_val = raw.get(f"{field}_fp")
        if fp_val is not None:
            try:
                return float(fp_val)
            except (TypeError, ValueError):
                pass

        # Last resort: legacy cents field (being removed March 12, 2026)
        cents_val = raw.get(field)
        if cents_val is not None:
            try:
                val = float(cents_val)
                # If it looks like cents (> 1), convert
                if val > 1.0:
                    return round(val / 100.0, 4)
                return val
            except (TypeError, ValueError):
                pass

        return None

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
