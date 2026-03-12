"""Core arbitrage detection engine.

Runs after every price refresh cycle. For each matched market pair,
checks if buying complementary positions across platforms yields a
guaranteed profit after fees.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import combinations

from backend.engine.fees import effective_cost, get_fee_schedule

logger = logging.getLogger(__name__)


@dataclass
class ArbLeg:
    platform: str
    market_id: str
    side: str  # "YES" or "NO"
    price: float
    fee_rate: float
    effective_cost: float
    available_size_usd: float


@dataclass
class ArbOpportunity:
    match_id: str
    question: str
    type: str  # "cross_platform"
    legs: list[ArbLeg]
    total_cost: float
    guaranteed_profit: float
    profit_after_fees: float
    profit_pct: float
    max_size_usd: float
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MarketPrices:
    """Price snapshot for arb calculations."""

    platform: str
    platform_id: str
    title: str
    yes_ask: float | None
    yes_bid: float | None
    no_ask: float | None
    no_bid: float | None
    yes_price: float = 0.0
    no_price: float = 0.0
    liquidity: float = 0.0


def detect_arbitrage(
    match_id: str,
    question: str,
    markets: list[MarketPrices],
    min_profit_pct: float = 1.0,
    min_profit_usd: float = 0.50,
    min_liquidity_usd: float = 50.0,
) -> list[ArbOpportunity]:
    """Detect cross-platform arbitrage opportunities for a matched set of markets.

    For every pair of markets from different platforms, checks both combinations:
    - YES on A + NO on B
    - NO on A + YES on B

    Returns opportunities where fee-adjusted profit exceeds thresholds.
    """
    opportunities: list[ArbOpportunity] = []

    for a, b in combinations(markets, 2):
        if a.platform == b.platform:
            continue

        # Option 1: YES on A + NO on B
        opp = _check_pair(
            match_id, question, a, b, "yes_a_no_b",
            min_profit_pct, min_profit_usd, min_liquidity_usd,
        )
        if opp:
            opportunities.append(opp)

        # Option 2: NO on A + YES on B
        opp = _check_pair(
            match_id, question, a, b, "no_a_yes_b",
            min_profit_pct, min_profit_usd, min_liquidity_usd,
        )
        if opp:
            opportunities.append(opp)

    return opportunities


def _check_pair(
    match_id: str,
    question: str,
    a: MarketPrices,
    b: MarketPrices,
    direction: str,
    min_profit_pct: float,
    min_profit_usd: float,
    min_liquidity_usd: float,
) -> ArbOpportunity | None:
    """Check one directional pairing for arb."""

    if direction == "yes_a_no_b":
        price_a = a.yes_ask or a.yes_price
        side_a = "YES"
        price_b = b.no_ask or b.no_price
        side_b = "NO"
    else:
        price_a = a.no_ask or a.no_price
        side_a = "NO"
        price_b = b.yes_ask or b.yes_price
        side_b = "YES"

    # Need valid prices on both sides
    if price_a is None or price_b is None:
        return None
    if price_a <= 0 or price_b <= 0:
        return None

    # Calculate effective costs with fees
    cost_a = effective_cost(price_a, a.platform)
    cost_b = effective_cost(price_b, b.platform)
    total_cost = cost_a + cost_b

    if total_cost >= 1.0:
        return None  # No arb

    raw_profit = 1.0 - total_cost

    # For conservative fee calc, also deduct the worst-case fee on the winning leg's payout
    # The winning leg pays $1.00 - entry_cost, and some platforms tax that profit
    fee_a = get_fee_schedule(a.platform)
    fee_b = get_fee_schedule(b.platform)
    worst_case_profit_fee = max(fee_a.profit_fee, fee_b.profit_fee)
    worst_case_withdrawal_fee = max(fee_a.withdrawal_fee, fee_b.withdrawal_fee)

    profit_after_fees = (
        raw_profit - (worst_case_profit_fee * raw_profit) - (worst_case_withdrawal_fee * 1.0)
    )
    profit_pct = (profit_after_fees / total_cost) * 100 if total_cost > 0 else 0.0

    if profit_after_fees < min_profit_usd / 100:
        # Normalize: min_profit_usd is per $1 contract, but our costs are per $1 payout
        pass

    if profit_pct < min_profit_pct:
        return None

    # Liquidity check
    size_a = a.liquidity if a.liquidity > 0 else float("inf")
    size_b = b.liquidity if b.liquidity > 0 else float("inf")
    max_size = min(size_a, size_b)

    if max_size < min_liquidity_usd and max_size != float("inf"):
        return None

    # Position sizing: each leg's fraction of total cost
    frac_a = cost_a / total_cost if total_cost > 0 else 0.5
    frac_b = cost_b / total_cost if total_cost > 0 else 0.5

    legs = [
        ArbLeg(
            platform=a.platform,
            market_id=a.platform_id,
            side=side_a,
            price=price_a,
            fee_rate=fee_a.taker_fee,
            effective_cost=cost_a,
            available_size_usd=a.liquidity,
            cost_fraction=round(frac_a, 4),
        ),
        ArbLeg(
            platform=b.platform,
            market_id=b.platform_id,
            side=side_b,
            price=price_b,
            fee_rate=fee_b.taker_fee,
            effective_cost=cost_b,
            available_size_usd=b.liquidity,
            cost_fraction=round(frac_b, 4),
        ),
    ]

    final_max_size = round(max_size, 2) if max_size != float("inf") else 0.0

    return ArbOpportunity(
        match_id=match_id,
        question=question,
        type="cross_platform",
        legs=legs,
        total_cost=round(total_cost, 6),
        guaranteed_profit=round(raw_profit, 6),
        profit_after_fees=round(profit_after_fees, 6),
        profit_pct=round(profit_pct, 2),
        max_size_usd=final_max_size,
    )
