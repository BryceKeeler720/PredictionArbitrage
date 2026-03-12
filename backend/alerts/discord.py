"""Discord webhook alert sender with cooldown deduplication."""

import hashlib
import logging
from datetime import UTC, datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings
from backend.engine.arbitrage import ArbOpportunity

logger = logging.getLogger(__name__)

# In-memory cooldown tracker (swap for Redis in production)
_alert_cooldowns: dict[str, datetime] = {}


def _opportunity_hash(opp: ArbOpportunity) -> str:
    """Create a deduplication key from the opportunity's legs."""
    parts = [opp.match_id]
    for leg in opp.legs:
        parts.extend([leg.platform, leg.market_id, leg.side])
    return hashlib.md5(":".join(parts).encode()).hexdigest()


def _is_on_cooldown(opp: ArbOpportunity) -> bool:
    """Check if this opportunity was recently alerted."""
    key = _opportunity_hash(opp)
    last_alert = _alert_cooldowns.get(key)
    if last_alert is None:
        return False
    elapsed = (datetime.now(UTC) - last_alert).total_seconds() / 60
    return elapsed < settings.alert_cooldown_minutes


def _mark_alerted(opp: ArbOpportunity) -> None:
    key = _opportunity_hash(opp)
    _alert_cooldowns[key] = datetime.now(UTC)


def _get_tier(profit_pct: float) -> tuple[str, str, int]:
    """Return (tier_name, webhook_url, embed_color) based on profit %."""
    if profit_pct >= 5.0:
        return "HIGH", settings.discord_webhook_high, 0xED4245  # Red
    elif profit_pct >= 3.0:
        return "MEDIUM", settings.discord_webhook_medium, 0xFEE75C  # Yellow
    else:
        return "LOW", settings.discord_webhook_low, 0x57F287  # Green


def _build_embed(opp: ArbOpportunity, tier: str) -> dict:
    """Build Discord embed payload."""
    leg_fields = []
    for i, leg in enumerate(opp.legs, 1):
        leg_fields.append({
            "name": f"Leg {i}",
            "value": f"Buy **{leg.side}** on **{leg.platform.title()}** @ ${leg.price:.3f}",
            "inline": True,
        })

    fields = [
        {"name": "Question", "value": opp.question[:200], "inline": False},
        *leg_fields,
        {
            "name": "Total Cost",
            "value": f"${opp.total_cost:.4f} per $1.00 payout",
            "inline": True,
        },
        {
            "name": "Profit (after fees)",
            "value": f"${opp.profit_after_fees:.4f} ({opp.profit_pct:.2f}%)",
            "inline": True,
        },
    ]

    if opp.max_size_usd > 0:
        thinnest = min(
            opp.legs,
            key=lambda leg: leg.available_size_usd if leg.available_size_usd > 0 else float("inf"),
        )
        fields.append({
            "name": "Max Size",
            "value": f"${opp.max_size_usd:,.0f} (limited by {thinnest.platform.title()} depth)",
            "inline": True,
        })

    emoji = {"HIGH": "\U0001f534", "MEDIUM": "\U0001f7e1", "LOW": "\U0001f7e2"}.get(tier, "")
    _, _, color = _get_tier(opp.profit_pct)

    return {
        "embeds": [{
            "title": f"{emoji} Arbitrage Opportunity — {tier}",
            "color": color,
            "fields": fields,
            "footer": {
                "text": (
                    f"PredArb \u2022 Detected at {opp.detected_at.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                ),
            },
        }]
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
async def _post_webhook(url: str, payload: dict) -> None:
    """Post to Discord webhook with retry on rate limits."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code == 429:
            retry_after = resp.json().get("retry_after", 5)
            logger.warning("Discord rate limited, retry after %ss", retry_after)
            import asyncio
            await asyncio.sleep(retry_after)
            raise Exception("Rate limited")  # Trigger retry
        resp.raise_for_status()


async def send_alert(opp: ArbOpportunity) -> bool:
    """Send a Discord alert for an arbitrage opportunity.

    Returns True if alert was sent, False if skipped (cooldown/no webhook).
    """
    if _is_on_cooldown(opp):
        logger.debug("Skipping alert for %s — on cooldown", opp.match_id)
        return False

    tier, webhook_url, _ = _get_tier(opp.profit_pct)

    if not webhook_url:
        # Fall back to any configured webhook
        webhook_url = (
            settings.discord_webhook_high
            or settings.discord_webhook_medium
            or settings.discord_webhook_low
        )
        if not webhook_url:
            logger.debug("No Discord webhook configured, skipping alert")
            return False

    payload = _build_embed(opp, tier)

    try:
        await _post_webhook(webhook_url, payload)
        _mark_alerted(opp)
        logger.info("Discord alert sent: %s (%.2f%% profit)", opp.question[:50], opp.profit_pct)
        return True
    except Exception:
        logger.exception("Failed to send Discord alert")
        return False
