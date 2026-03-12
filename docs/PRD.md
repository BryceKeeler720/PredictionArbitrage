# Prediction Market Arbitrage Scanner — Product Requirements Document

## 1. Overview

**Project Name:** PredArb  
**Owner:** Bryce Keeler  
**Deployment Target:** Self-hosted on Bryce's Proxmox homelab (LXC container)  
**Stack:** Python (FastAPI backend), React frontend, PostgreSQL (existing Supabase instance), Redis for caching  

PredArb is a self-hosted web application that continuously scans multiple prediction market platforms for arbitrage opportunities. When the combined cost of buying complementary positions across platforms is less than the guaranteed payout, the system identifies the opportunity, calculates expected profit, and sends a Discord webhook alert. A local dashboard provides real-time visibility into all tracked markets, active opportunities, and historical performance.

---

## 2. Problem Statement

Prediction markets like Polymarket, Kalshi, Manifold, and PredictIt price the same or equivalent events independently. Because these platforms have fragmented liquidity, different user bases, and varying fee structures, price discrepancies regularly emerge. Unlike tightly managed sportsbooks, prediction markets often have wider spreads and slower price discovery, creating persistent arbitrage windows.

Currently there is no free, self-hosted tool that:
- Normalizes market data across platforms into a unified schema
- Automatically detects cross-platform arbitrage on equivalent events
- Accounts for platform-specific fees in profit calculations
- Alerts a user in real time via Discord

---

## 3. Target Platforms (Phase 1)

| Platform | API Type | Auth Required for Read? | Base URL |
|---|---|---|---|
| **Polymarket** | REST + WebSocket | No (public CLOB + Gamma endpoints) | `https://gamma-api.polymarket.com`, `https://clob.polymarket.com` |
| **Kalshi** | REST + WebSocket | No for market data | `https://api.elections.kalshi.com/trade-api/v2` |
| **Manifold** | REST | No for public markets | `https://api.manifold.markets/v0` |
| **PredictIt** | REST | No for market data | `https://www.predictit.org/api/marketdata/all` |

### Phase 2 (Future)
- Robinhood (Kalshi-powered, may deduplicate)
- Metaculus (forecasting, no trading — useful as a "fair value" signal)
- OddsPapi / sportsbook cross-reference for sports prediction markets

---

## 4. Core Architecture

```
┌──────────────────────────────────────────────────────┐
│                    PredArb System                     │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────┐    ┌──────────────┐                │
│  │  Scheduler   │───▶│  Collectors   │                │
│  │  (APScheduler│    │  (per-platform│                │
│  │   or cron)  │    │   adapters)  │                │
│  └─────────────┘    └──────┬───────┘                │
│                            │                         │
│                     ┌──────▼───────┐                │
│                     │  Normalizer   │                │
│                     │  (unified     │                │
│                     │   market      │                │
│                     │   schema)     │                │
│                     └──────┬───────┘                │
│                            │                         │
│               ┌────────────▼────────────┐           │
│               │    Market Matcher        │           │
│               │  (fuzzy title + slug     │           │
│               │   matching, manual       │           │
│               │   override table)        │           │
│               └────────────┬────────────┘           │
│                            │                         │
│               ┌────────────▼────────────┐           │
│               │   Arbitrage Engine       │           │
│               │  • Cross-platform arb    │           │
│               │  • Same-platform spread  │           │
│               │  • Fee-adjusted profit   │           │
│               │  • Liquidity check       │           │
│               └────────────┬────────────┘           │
│                            │                         │
│          ┌─────────────────┼─────────────────┐      │
│          ▼                 ▼                 ▼      │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────┐  │
│  │   Discord     │ │   PostgreSQL  │ │   FastAPI   │  │
│  │   Webhooks    │ │   (history +  │ │   + React   │  │
│  │              │ │    matches)   │ │  Dashboard  │  │
│  └──────────────┘ └──────────────┘ └────────────┘  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 5. Data Models

### 5.1 Unified Market

```python
class NormalizedMarket:
    id: str                    # Internal UUID
    platform: str              # "polymarket" | "kalshi" | "manifold" | "predictit"
    platform_id: str           # Native ID/ticker on the platform
    title: str                 # Human-readable question
    slug: str                  # URL-safe slug for matching
    category: str              # "politics" | "sports" | "crypto" | "economics" | ...
    yes_price: float           # 0.0 - 1.0 (probability)
    no_price: float            # 0.0 - 1.0
    yes_ask: float | None      # Best ask for YES
    yes_bid: float | None      # Best bid for YES
    no_ask: float | None       # Best ask for NO
    no_bid: float | None       # Best bid for NO
    volume_24h: float          # In USD equivalent
    liquidity: float           # Available depth at best price (USD)
    open_interest: float | None
    close_time: datetime | None
    last_updated: datetime
    source_url: str            # Direct link to market
    raw_data: dict             # Full API response for debugging
```

### 5.2 Market Match

```python
class MarketMatch:
    id: str
    canonical_question: str     # Cleaned, normalized question text
    markets: list[NormalizedMarket]  # 2+ markets from different platforms
    match_confidence: float     # 0.0 - 1.0
    match_method: str           # "auto_fuzzy" | "auto_slug" | "manual"
    created_at: datetime
    verified: bool              # Human-confirmed match
```

### 5.3 Arbitrage Opportunity

```python
class ArbitrageOpportunity:
    id: str
    match_id: str               # FK to MarketMatch
    type: str                   # "cross_platform" | "same_event_spread"
    legs: list[ArbLeg]          # Buy YES on platform A, Buy NO on platform B
    total_cost: float           # Sum of leg costs (per $1 payout)
    guaranteed_profit: float    # 1.0 - total_cost (before fees)
    profit_after_fees: float    # After platform-specific fees
    profit_pct: float           # profit_after_fees / total_cost * 100
    max_size_usd: float         # Limited by thinnest leg liquidity
    detected_at: datetime
    expired_at: datetime | None # When prices moved and arb closed
    status: str                 # "active" | "expired" | "executed"
```

### 5.4 Arb Leg

```python
class ArbLeg:
    platform: str
    market_id: str
    side: str                   # "YES" | "NO"
    price: float                # Entry price
    fee_rate: float             # Platform fee as decimal
    effective_cost: float       # price + fees
    available_size_usd: float   # Depth at this price level
```

---

## 6. Platform Fee Schedule

Fees must be factored into every arbitrage calculation. Maintain as config:

```yaml
fees:
  polymarket:
    maker_fee: 0.00            # Makers earn rebates
    taker_fee: 0.02            # 2% on taker orders
    settlement_fee: 0.00
    notes: "Fees on proceeds; no fee if position loses"
  kalshi:
    maker_fee: 0.00
    taker_fee: 0.02            # ~2 cents per contract
    settlement_fee: 0.00
    notes: "Fee waived if held to settlement and wins"
  manifold:
    maker_fee: 0.00
    taker_fee: 0.00            # Play money — no real fees
    settlement_fee: 0.00
    notes: "Play money platform; useful for signal only"
  predictit:
    profit_fee: 0.10           # 10% on profits
    withdrawal_fee: 0.05       # 5% on withdrawals
    settlement_fee: 0.00
    notes: "Effective ~15.5% drag; must factor heavily"
```

---

## 7. Arbitrage Detection Logic

### 7.1 Cross-Platform Binary Arb

For a matched binary event across platforms A and B:

```
cost = best_ask_yes_A + best_ask_no_B
# or
cost = best_ask_no_A + best_ask_yes_B

# Pick the cheaper combination
if cost < 1.0:
    raw_profit = 1.0 - cost
    # Apply fees to the winning leg (since you don't know which wins)
    worst_case_fee = max(fee_A, fee_B)
    profit_after_fees = raw_profit - worst_case_fee
    if profit_after_fees > MIN_PROFIT_THRESHOLD:
        ALERT!
```

### 7.2 Same-Platform Spread Arb (rare but possible)

If a platform has multiple related markets that should sum to 100% but don't:

```
# Multi-outcome event: outcomes A, B, C, D
total_no_cost = sum(best_ask_no for each outcome)
if total_no_cost < (num_outcomes - 1):
    # Arb exists by buying NO on all outcomes
    profit = (num_outcomes - 1) - total_no_cost
```

### 7.3 Configurable Thresholds

```yaml
thresholds:
  min_profit_pct: 1.0          # Minimum 1% profit after fees
  min_profit_usd: 0.50         # Minimum $0.50 absolute profit
  min_liquidity_usd: 50.0      # Ignore illiquid markets
  max_time_to_close_days: 365  # Ignore very long-dated markets
  min_volume_24h: 100.0        # Ignore dead markets
  alert_cooldown_minutes: 30   # Don't re-alert same opportunity
```

---

## 8. Market Matching Strategy

This is the hardest part. Same events are named differently across platforms.

### 8.1 Automatic Matching

1. **Slug normalization**: Strip punctuation, lowercase, remove common words ("will", "the", "be"), stem remaining words
2. **TF-IDF + cosine similarity**: Compare normalized titles; threshold at 0.85 confidence
3. **Category + date filtering**: Only compare markets in the same category with overlapping close dates
4. **Entity extraction**: Pull out key entities (person names, organizations, numbers, dates) and require overlap

### 8.2 Manual Override Table

```sql
CREATE TABLE market_match_overrides (
    platform_a TEXT NOT NULL,
    market_id_a TEXT NOT NULL,
    platform_b TEXT NOT NULL,
    market_id_b TEXT NOT NULL,
    canonical_question TEXT,
    created_by TEXT DEFAULT 'manual',
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 8.3 LLM-Assisted Matching (Optional Phase 2)

Use a local LLM (or Claude API) to evaluate candidate pairs and confirm semantic equivalence. Useful for tricky cases like "Will Trump win 2028?" vs "2028 Presidential Election Winner" where the Polymarket version might have multiple outcome tokens.

---

## 9. Discord Webhook Integration

### 9.1 Alert Payload

```json
{
  "embeds": [{
    "title": "🚨 Arbitrage Opportunity Detected",
    "color": 3066993,
    "fields": [
      { "name": "Question", "value": "Will X happen?", "inline": false },
      { "name": "Leg 1", "value": "Buy YES on Polymarket @ $0.42", "inline": true },
      { "name": "Leg 2", "value": "Buy NO on Kalshi @ $0.52", "inline": true },
      { "name": "Total Cost", "value": "$0.94 per $1.00 payout", "inline": true },
      { "name": "Profit (after fees)", "value": "$0.04 (4.26%)", "inline": true },
      { "name": "Max Size", "value": "$500 (limited by Kalshi depth)", "inline": true },
      { "name": "Time to Close", "value": "14 days", "inline": true }
    ],
    "footer": { "text": "PredArb • Detected at 2026-03-11T14:30:00Z" },
    "url": "http://predarb.local/opportunity/abc123"
  }]
}
```

### 9.2 Alert Tiers

| Tier | Condition | Behavior |
|---|---|---|
| **🟢 Low** | 1-3% profit after fees | Post to `#arb-low` channel |
| **🟡 Medium** | 3-5% profit after fees | Post to `#arb-medium` channel |
| **🔴 High** | >5% profit after fees | Post to `#arb-high` channel + @mention role |

### 9.3 Digest Mode

Daily summary at 8:00 AM CT:
- Total opportunities detected in last 24h
- Best opportunity (highest profit %)
- Average arb duration before expiry
- Platform pair with most opportunities

---

## 10. Dashboard (React Frontend)

### 10.1 Pages

**Home / Dashboard**
- Active opportunities sorted by profit % (table with expandable rows)
- Sparkline charts showing price convergence over time
- Platform status indicators (API health, last successful fetch)

**Market Explorer**
- Browse all tracked markets across platforms
- Filter by platform, category, status
- See matched markets side-by-side with price comparison

**Opportunity Detail**
- Full leg breakdown with fee calculations
- Price history chart for both legs
- Liquidity depth visualization
- Links to both platform pages

**Match Manager**
- View auto-matched market pairs with confidence scores
- Approve/reject matches
- Add manual matches
- Search for unmatched markets

**Settings**
- Configure thresholds (min profit, min liquidity, etc.)
- Manage Discord webhook URLs
- API key management for authenticated platforms
- Polling interval configuration

### 10.2 Tech Stack
- React 18+ with TypeScript
- Tailwind CSS
- Recharts for data visualization
- TanStack Query for data fetching
- Served by FastAPI (or Caddy reverse proxy)

---

## 11. API Endpoints (FastAPI)

```
GET  /api/v1/opportunities              # List active arb opportunities
GET  /api/v1/opportunities/{id}         # Opportunity detail
GET  /api/v1/markets                    # All tracked markets (paginated)
GET  /api/v1/markets/{platform}/{id}    # Specific market detail
GET  /api/v1/matches                    # All market matches
POST /api/v1/matches                    # Create manual match
PUT  /api/v1/matches/{id}/verify        # Verify/reject auto match
GET  /api/v1/stats                      # Dashboard stats
GET  /api/v1/health                     # System + per-platform health
GET  /api/v1/config                     # Current thresholds
PUT  /api/v1/config                     # Update thresholds
POST /api/v1/webhooks/test              # Send test Discord message
```

---

## 12. Deployment & Infrastructure

### 12.1 Homelab Target

- **Host:** Proxmox LXC container (Ubuntu or Alpine)
- **Database:** Existing Supabase/PostgreSQL instance (or dedicated Postgres container)
- **Cache:** Redis container (for rate limiting, deduplication, WebSocket state)
- **Reverse Proxy:** Caddy or Nginx (Tailscale for remote access)
- **Process Manager:** systemd services or Docker Compose

### 12.2 Resource Estimates

- CPU: Minimal (API polling, not compute-heavy)
- RAM: ~256MB-512MB for the app + Redis
- Disk: ~1GB for database (grows slowly with historical data)
- Network: ~50-100 API calls/minute across all platforms

### 12.3 Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/predarb

# Redis
REDIS_URL=redis://localhost:6379/0

# Discord
DISCORD_WEBHOOK_LOW=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_MEDIUM=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_HIGH=https://discord.com/api/webhooks/...

# Platform API Keys (only needed for authenticated endpoints)
KALSHI_API_KEY=
KALSHI_API_SECRET=
POLYMARKET_PRIVATE_KEY=

# App Config
POLL_INTERVAL_SECONDS=60
MIN_PROFIT_PCT=1.0
MIN_LIQUIDITY_USD=50.0
LOG_LEVEL=INFO
```

---

## 13. Polling & Rate Limit Strategy

| Platform | Rate Limit | Strategy |
|---|---|---|
| Polymarket | Not published; be conservative | Poll Gamma `/markets` every 60s; CLOB `/price` for matched markets every 30s |
| Kalshi | Published in docs | Poll `/markets` with pagination every 60s; orderbook for matched every 30s |
| Manifold | 500 req/min | Poll `/markets` every 120s (play money, lower priority) |
| PredictIt | Generous | Poll `/marketdata/all` every 120s (single endpoint returns everything) |

WebSocket connections for Polymarket and Kalshi should be Phase 2 — start with REST polling for simplicity.

---

## 14. Development Phases

### Phase 1: MVP (Weeks 1-3)
- [ ] Platform collectors: Polymarket (Gamma + CLOB), Kalshi, PredictIt
- [ ] Normalized market schema + PostgreSQL storage
- [ ] Basic fuzzy title matching
- [ ] Cross-platform binary arb detection with fee adjustment
- [ ] Discord webhook alerts (single channel)
- [ ] Minimal FastAPI dashboard (JSON API only, no frontend)
- [ ] Systemd service for continuous polling

### Phase 2: Dashboard (Weeks 4-5)
- [ ] React frontend with opportunity table
- [ ] Market explorer with side-by-side comparison
- [ ] Manual match management UI
- [ ] Price history charts
- [ ] Settings page

### Phase 3: Intelligence (Weeks 6-8)
- [ ] Manifold collector (signal source, not arb target)
- [ ] Improved matching (TF-IDF, entity extraction)
- [ ] WebSocket connections for real-time pricing
- [ ] Multi-outcome event arb (not just binary)
- [ ] Tiered Discord alerts with daily digest
- [ ] Backtesting module (how long do arbs persist? what's average profit?)

### Phase 4: Advanced (Ongoing)
- [ ] LLM-assisted market matching
- [ ] Sportsbook cross-reference (OddsPapi integration)
- [ ] Auto-execution (requires funded accounts + careful risk management)
- [ ] Telegram bot alternative to Discord
- [ ] Mobile-friendly PWA dashboard

---

## 15. Risk & Legal Considerations

- **Not financial advice.** This tool identifies pricing discrepancies; execution involves real financial risk.
- **Platform ToS:** Some platforms may restrict automated trading or cross-platform strategies. Review ToS for Kalshi and Polymarket.
- **Execution risk:** Prices can move between detection and execution. Arb may disappear by the time you manually place orders.
- **Counterparty risk:** Prediction markets can have resolution disputes. An "arb" can fail if platforms resolve the same event differently.
- **PredictIt fees:** The 10% profit + 5% withdrawal fee structure makes PredictIt arbs only viable at much higher spreads (~16%+ gross).
- **Regulatory:** Kalshi is CFTC-regulated. Polymarket recently re-entered the US. Be aware of your state's restrictions.

---

## 16. Success Metrics

- **Detection latency:** Time from price change to opportunity detection < 90 seconds
- **Match accuracy:** >90% of auto-matched markets are semantically equivalent
- **False positive rate:** <10% of alerts are non-actionable (stale price, resolution mismatch, etc.)
- **Uptime:** Scanner running >99% of the time
- **Opportunities found:** Track count, average profit, and average duration