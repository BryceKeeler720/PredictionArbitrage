---
name: prediction-arb
description: >
  Skill for building and maintaining PredArb, a self-hosted prediction market arbitrage scanner.
  Use this skill whenever working on the PredArb codebase — including platform API collectors
  (Polymarket, Kalshi, Manifold, PredictIt), market normalization, fuzzy matching, arbitrage
  detection engine, Discord webhook alerts, FastAPI backend, React dashboard, or deployment
  to Proxmox homelab. Trigger on mentions of prediction markets, arbitrage scanning, cross-platform
  price comparison, market matching, arb detection, Discord alerts for trading opportunities,
  or any component described in the PredArb PRD. Also trigger when the user mentions "arb scanner",
  "prediction market tool", "price discrepancy finder", or references Polymarket/Kalshi/Manifold/PredictIt
  API integration work.
---

# PredArb — Prediction Market Arbitrage Scanner

## Quick Context

PredArb is a self-hosted Python/React application that scans Polymarket, Kalshi, Manifold, and PredictIt for cross-platform arbitrage opportunities on equivalent prediction markets. It normalizes prices, matches equivalent markets across platforms, calculates fee-adjusted profit, and sends Discord webhook alerts.

**Read the full PRD first:** `docs/PRD.md` — it contains the complete data models, architecture, API specifications, fee schedules, and phased development plan.

---

## Project Structure

```
predarb/
├── docs/
│   └── PRD.md                    # Full product requirements document
├── backend/
│   ├── main.py                   # FastAPI app entrypoint
│   ├── config.py                 # Settings, thresholds, env vars (Pydantic BaseSettings)
│   ├── db.py                     # SQLAlchemy/asyncpg setup
│   ├── models/
│   │   ├── market.py             # NormalizedMarket, MarketMatch ORM models
│   │   ├── opportunity.py        # ArbitrageOpportunity, ArbLeg models
│   │   └── config.py             # Runtime config model
│   ├── collectors/
│   │   ├── base.py               # Abstract BaseCollector class
│   │   ├── polymarket.py         # Polymarket Gamma + CLOB collector
│   │   ├── kalshi.py             # Kalshi REST collector
│   │   ├── manifold.py           # Manifold Markets collector
│   │   └── predictit.py          # PredictIt collector
│   ├── matching/
│   │   ├── normalizer.py         # Text normalization (slug, stemming, stop words)
│   │   ├── matcher.py            # TF-IDF + cosine similarity matching engine
│   │   └── overrides.py          # Manual match override CRUD
│   ├── engine/
│   │   ├── arbitrage.py          # Core arb detection logic
│   │   ├── fees.py               # Per-platform fee calculator
│   │   └── scheduler.py          # APScheduler job setup
│   ├── alerts/
│   │   ├── discord.py            # Discord webhook sender
│   │   └── digest.py             # Daily digest generator
│   ├── api/
│   │   ├── routes/
│   │   │   ├── opportunities.py
│   │   │   ├── markets.py
│   │   │   ├── matches.py
│   │   │   ├── stats.py
│   │   │   ├── config.py
│   │   │   └── health.py
│   │   └── deps.py               # Dependency injection
│   └── migrations/               # Alembic migrations
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── MarketExplorer.tsx
│   │   │   ├── OpportunityDetail.tsx
│   │   │   ├── MatchManager.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   │   ├── OpportunityTable.tsx
│   │   │   ├── PriceChart.tsx
│   │   │   ├── PlatformStatus.tsx
│   │   │   └── MatchCard.tsx
│   │   └── hooks/
│   │       └── useApi.ts
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Key Technical Decisions

### Platform Collectors

Each collector extends `BaseCollector` with:
- `fetch_markets() -> list[NormalizedMarket]` — pull all active markets
- `fetch_prices(market_ids: list[str]) -> dict[str, PriceData]` — targeted price refresh for matched markets
- `platform_name: str` — identifier
- `rate_limiter` — per-platform rate limiting via Redis

**Polymarket specifics:**
- Use Gamma API (`GET /markets?closed=false`) for market discovery
- Use CLOB API (`GET /price`, `GET /book`) for real-time pricing
- Token IDs link Gamma markets to CLOB orderbook
- `yes_price` = CLOB midpoint for YES token; `no_price` = 1 - yes_price (or CLOB midpoint for NO token)
- No auth needed for read-only data

**Kalshi specifics:**
- Base URL: `https://api.elections.kalshi.com/trade-api/v2`
- `GET /markets?status=open&limit=1000` with cursor pagination
- Response includes `yes_bid`, `yes_ask`, `no_bid`, `no_ask` directly
- Prices in cents (divide by 100 to normalize to 0-1)
- Note: Legacy integer fields being removed March 12, 2026 — use `_dollars` and `_fp` fields

**PredictIt specifics:**
- Single endpoint returns all markets: `GET /api/marketdata/all`
- Prices already in 0-1 range
- `BestBuyYesCost`, `BestBuyNoCost`, `BestSellYesCost`, `BestSellNoCost` per contract
- Heavy fee drag (10% profit + 5% withdrawal) — only flag arbs >16% gross

**Manifold specifics:**
- `GET /markets?limit=1000` returns markets with `probability` field
- Play money only — use as a probability signal, not an arb target
- 500 req/min rate limit is generous

### Market Matching

This is the most complex and error-prone component. Strategy:

1. **Pre-filter**: Only compare markets in same category with overlapping timeframes
2. **Normalize titles**: Lowercase, strip punctuation, remove stop words ("will", "the", "be", "a", "by"), stem with NLTK PorterStemmer
3. **TF-IDF similarity**: Compute on normalized titles, threshold at 0.80 for candidates
4. **Entity overlap**: Extract named entities (spaCy or regex for names/dates/numbers), require >50% entity overlap
5. **Manual review queue**: Matches at 0.80-0.90 confidence go to the Match Manager UI for human verification
6. **Override table**: Hard-coded matches for known equivalencies that fuzzy matching struggles with

### Arbitrage Engine

The engine runs after every price refresh cycle:

```python
for match in active_matches:
    markets = match.markets  # list of NormalizedMarket from different platforms
    for (a, b) in combinations(markets, 2):
        # Option 1: YES on A + NO on B
        cost_1 = effective_cost(a.yes_ask, a.platform) + effective_cost(b.no_ask, b.platform)
        # Option 2: NO on A + YES on B  
        cost_2 = effective_cost(a.no_ask, a.platform) + effective_cost(b.yes_ask, b.platform)
        
        best_cost = min(cost_1, cost_2)
        if best_cost < 1.0:
            profit = 1.0 - best_cost
            if profit > config.min_profit_threshold:
                create_opportunity(match, legs, profit)
                send_discord_alert(opportunity)
```

**Fee calculation must be conservative:**
- Apply taker fees to both legs (worst case)
- For PredictIt, apply 10% profit fee to the winning leg
- For Polymarket, fees are on proceeds — model as fee on the $1.00 payout of winning leg

### Discord Webhooks

Use `httpx` to POST to Discord webhook URLs. Embed format specified in PRD section 9.

Key implementation details:
- Cooldown per opportunity (30 min default) — don't spam same arb
- Deduplication via Redis: hash of (match_id, leg_combination) with TTL
- Retry with exponential backoff on Discord rate limits (429 responses)
- Daily digest job at 8:00 AM CT via APScheduler

---

## Development Workflow

### Getting Started

```bash
# Clone and setup
cd predarb
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Database
alembic upgrade head

# Environment
cp .env.example .env
# Fill in DISCORD_WEBHOOK_* URLs

# Run
uvicorn backend.main:app --reload --port 8420

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

### Testing Collectors

Each collector should have integration tests that hit the real APIs (with aggressive caching):

```bash
# Test individual collector
python -m pytest tests/collectors/test_polymarket.py -v

# Test matching engine
python -m pytest tests/matching/ -v

# Test arb detection with mock data
python -m pytest tests/engine/ -v
```

### Deployment to Homelab

Target: Proxmox LXC container with Docker Compose.

```bash
# On the LXC container
docker compose up -d

# Or with systemd
sudo systemctl enable predarb
sudo systemctl start predarb
```

Access via Tailscale: `http://predarb.tail-net:8420`

---

## Common Patterns & Pitfalls

1. **Price staleness**: Always check `last_updated` on prices. If >5 minutes old, skip the arb calculation — the opportunity is likely gone.

2. **Resolution ambiguity**: "Will Bitcoin hit $100k in 2026?" on Polymarket might resolve at a different time or with different criteria than the Kalshi equivalent. The match manager exists to catch these.

3. **Liquidity illusion**: A market might show a great price but with $5 of depth. Always check `available_size_usd` on each leg and cap the arb size at the minimum.

4. **PredictIt position limits**: PredictIt caps positions at $3,500 per contract. Factor this into max arb size.

5. **Polymarket token structure**: Polymarket binary markets have two tokens (YES and NO). The CLOB has separate orderbooks for each token. Make sure you're fetching both when computing spreads.

6. **Kalshi's field migration**: As of March 2026, Kalshi is removing legacy integer fields. Always use `yes_bid_dollars`, `yes_ask_dollars`, etc.

7. **Time zones**: Normalize all timestamps to UTC. Close times are critical for matching — two markets about the "same" event but with different close dates are NOT equivalent.

---

## Configuration Reference

See `backend/config.py` for all settings. Key ones:

```python
class Settings(BaseSettings):
    # Polling
    poll_interval_seconds: int = 60
    price_refresh_seconds: int = 30
    
    # Thresholds
    min_profit_pct: float = 1.0
    min_profit_usd: float = 0.50
    min_liquidity_usd: float = 50.0
    max_time_to_close_days: int = 365
    min_volume_24h: float = 100.0
    
    # Matching
    match_confidence_threshold: float = 0.80
    auto_verify_threshold: float = 0.95
    
    # Alerts
    alert_cooldown_minutes: int = 30
    daily_digest_hour: int = 8  # CT
    discord_webhook_low: str = ""
    discord_webhook_medium: str = ""
    discord_webhook_high: str = ""
    
    # Database
    database_url: str = "postgresql+asyncpg://..."
    redis_url: str = "redis://localhost:6379/0"
```