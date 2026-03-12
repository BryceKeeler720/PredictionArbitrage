"""PredictIt collector — single endpoint returns all markets.

PredictIt has heavy fee drag (10% profit + 5% withdrawal), so arbs need >16% gross to be profitable.
"""

import contextlib
import logging
from datetime import datetime

from backend.collectors.base import BaseCollector, MarketData

logger = logging.getLogger(__name__)

PREDICTIT_BASE = "https://www.predictit.org/api/marketdata/all"


class PredictItCollector(BaseCollector):
    platform_name = "predictit"
    base_url = PREDICTIT_BASE

    async def fetch_markets(self) -> list[MarketData]:
        """Fetch all markets from the single PredictIt endpoint."""
        try:
            data = await self._get(PREDICTIT_BASE)
        except Exception:
            logger.exception("PredictIt fetch failed")
            return []

        markets_raw = data.get("markets", []) if isinstance(data, dict) else []
        all_markets: list[MarketData] = []

        for market_raw in markets_raw:
            contracts = market_raw.get("contracts", [])
            market_id = str(market_raw.get("id", ""))
            market_name = market_raw.get("name", "") or market_raw.get("shortName", "")
            market_url = market_raw.get("url", "")

            # For binary markets (single contract), emit one MarketData
            # For multi-outcome markets, emit one per contract
            if len(contracts) == 1:
                c = contracts[0]
                m = self._parse_contract(c, market_id, market_name, market_url, market_raw)
                if m:
                    all_markets.append(m)
            else:
                # Multi-contract market — each contract is a separate outcome
                for c in contracts:
                    contract_name = c.get("name", "") or c.get("shortName", "")
                    full_title = f"{market_name}: {contract_name}" if contract_name else market_name
                    cid = str(c.get("id", ""))
                    m = self._parse_contract(
                        c, f"{market_id}-{cid}", full_title, market_url, market_raw
                    )
                    if m:
                        all_markets.append(m)

        logger.info("PredictIt: fetched %d markets", len(all_markets))
        return all_markets

    async def fetch_prices(self, market_ids: list[str]) -> dict[str, MarketData]:
        """Re-fetch all markets and filter to requested IDs.

        PredictIt has a single endpoint so we always get everything.
        """
        all_markets = await self.fetch_markets()
        return {m.platform_id: m for m in all_markets if m.platform_id in market_ids}

    def _parse_contract(
        self,
        contract: dict,
        platform_id: str,
        title: str,
        source_url: str,
        market_raw: dict,
    ) -> MarketData | None:
        if not title or not platform_id:
            return None

        yes_ask = self._safe_float(contract.get("bestBuyYesCost"))
        yes_bid = self._safe_float(contract.get("bestSellYesCost"))
        no_ask = self._safe_float(contract.get("bestBuyNoCost"))
        no_bid = self._safe_float(contract.get("bestSellNoCost"))
        last_price = self._safe_float(contract.get("lastTradePrice"))

        yes_price = last_price if last_price else (yes_ask if yes_ask else 0.0)
        no_price = round(1.0 - yes_price, 4) if yes_price else 0.0

        # Parse close time
        close_time = None
        end_date = market_raw.get("dateEnd")
        if end_date:
            with contextlib.suppress(ValueError, AttributeError):
                close_time = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        volume = self._safe_float(contract.get("totalSharesTraded", 0))

        return MarketData(
            platform="predictit",
            platform_id=platform_id,
            title=title,
            slug=platform_id,
            category="politics",  # PredictIt is almost entirely political markets
            yes_price=yes_price,
            no_price=no_price,
            yes_ask=yes_ask if yes_ask else None,
            yes_bid=yes_bid if yes_bid else None,
            no_ask=no_ask if no_ask else None,
            no_bid=no_bid if no_bid else None,
            volume_24h=volume,
            liquidity=0.0,  # PredictIt doesn't expose depth
            close_time=close_time,
            source_url=source_url,
            raw_data=contract,
        )

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
