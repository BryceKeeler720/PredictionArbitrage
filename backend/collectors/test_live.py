"""Quick script to test collectors against live APIs (no DB required)."""

import asyncio
import sys


async def test_polymarket() -> None:
    from backend.collectors.polymarket import PolymarketCollector

    print("=" * 60)
    print("Testing Polymarket collector...")
    print("=" * 60)

    collector = PolymarketCollector()
    try:
        markets = await collector.fetch_markets()
        print(f"Fetched {len(markets)} markets\n")

        # Show top 5 by volume
        markets.sort(key=lambda m: m.volume_24h, reverse=True)
        for m in markets[:5]:
            print(f"  [{m.platform_id[:12]}...] {m.title[:70]}")
            print(f"    YES: {m.yes_price:.3f}  NO: {m.no_price:.3f}  Vol24h: ${m.volume_24h:,.0f}")
            print(f"    Category: {m.category}  Close: {m.close_time}")
            print()
    finally:
        await collector.close()


async def test_kalshi() -> None:
    from backend.collectors.kalshi import KalshiCollector

    print("=" * 60)
    print("Testing Kalshi collector...")
    print("=" * 60)

    collector = KalshiCollector()
    try:
        markets = await collector.fetch_markets()
        print(f"Fetched {len(markets)} markets\n")

        # Show top 5 by volume
        markets.sort(key=lambda m: m.volume_24h, reverse=True)
        for m in markets[:5]:
            print(f"  [{m.platform_id}] {m.title[:70]}")
            print(f"    YES: {m.yes_price:.3f}  NO: {m.no_price:.3f}  Vol24h: ${m.volume_24h:,.0f}")
            print(f"    Ask/Bid: yes_ask={m.yes_ask} yes_bid={m.yes_bid}")
            print(f"    Category: {m.category}  Close: {m.close_time}")
            print()
    finally:
        await collector.close()


async def main() -> None:
    platforms = sys.argv[1:] if len(sys.argv) > 1 else ["polymarket", "kalshi"]

    if "polymarket" in platforms:
        await test_polymarket()

    if "kalshi" in platforms:
        await test_kalshi()


if __name__ == "__main__":
    asyncio.run(main())
