"""Per-platform fee calculator.

Fees must be applied conservatively — always assume taker fees on both legs.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FeeSchedule:
    taker_fee: float  # Applied to entry cost
    profit_fee: float  # Applied to profit (PredictIt-style)
    withdrawal_fee: float  # Applied to withdrawal (PredictIt-style)
    settlement_fee: float


# Fee schedules per platform
PLATFORM_FEES: dict[str, FeeSchedule] = {
    "polymarket": FeeSchedule(
        taker_fee=0.02,  # 2% on taker orders
        profit_fee=0.0,
        withdrawal_fee=0.0,
        settlement_fee=0.0,
    ),
    "kalshi": FeeSchedule(
        taker_fee=0.02,  # ~2 cents per contract
        profit_fee=0.0,
        withdrawal_fee=0.0,
        settlement_fee=0.0,
    ),
    "predictit": FeeSchedule(
        taker_fee=0.0,  # No entry fee, but heavy profit/withdrawal fees
        profit_fee=0.10,  # 10% on profits
        withdrawal_fee=0.05,  # 5% on withdrawals
        settlement_fee=0.0,
    ),
    "manifold": FeeSchedule(
        taker_fee=0.0,  # Play money
        profit_fee=0.0,
        withdrawal_fee=0.0,
        settlement_fee=0.0,
    ),
}


def get_fee_schedule(platform: str) -> FeeSchedule:
    return PLATFORM_FEES.get(platform, FeeSchedule(0.0, 0.0, 0.0, 0.0))


def effective_cost(price: float, platform: str) -> float:
    """Calculate the effective cost of buying a position at `price` on `platform`.

    For most platforms, this is price + taker_fee applied to the price.
    For PredictIt, entry is at face value but profits are taxed — modeled differently.
    """
    fees = get_fee_schedule(platform)

    if platform == "predictit":
        # PredictIt: no entry fee, but 10% profit fee on winnings
        # If you buy YES at 0.40 and it resolves YES, you get $1.00
        # Profit = $0.60, fee = $0.06, net = $0.94
        # Effective cost = price (entry) + profit_fee * (1 - price)
        # This models worst-case: the leg wins
        return price + fees.profit_fee * (1.0 - price)
    else:
        # Standard: taker fee on the entry price
        return price * (1.0 + fees.taker_fee)


def effective_payout(platform: str) -> float:
    """What you actually receive per $1.00 contract payout after fees."""
    fees = get_fee_schedule(platform)

    if platform == "predictit":
        # After withdrawal fee on the full amount
        return 1.0 * (1.0 - fees.withdrawal_fee)
    return 1.0  # Other platforms pay $1.00 on settlement
