# CLAUDE.md — PredArb Project

## What is this?

PredArb is a self-hosted prediction market arbitrage scanner. It polls Polymarket, Kalshi, PredictIt, and Manifold APIs, normalizes prices, matches equivalent markets across platforms, detects fee-adjusted arbitrage, and sends Discord webhook alerts.

## Key files to read first

- `docs/PRD.md` — Full product requirements, data models, architecture, fee schedules, and phased plan
- `skill/SKILL.md` — Technical implementation guide, project structure, collector patterns, and common pitfalls

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy (async), APScheduler, httpx, scikit-learn (TF-IDF matching)
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Recharts, TanStack Query
- **Database:** PostgreSQL (via existing Supabase instance or dedicated container)
- **Cache:** Redis (rate limiting, alert deduplication)
- **Deployment:** Docker Compose on Proxmox LXC, Tailscale for access

## Architecture summary

```
Scheduler → Collectors (per-platform) → Normalizer → Matcher → Arb Engine → Discord Alerts
                                                                           → PostgreSQL
                                                                           → FastAPI → React Dashboard
```

## Commands

```bash
# Backend
uvicorn backend.main:app --reload --port 8420
alembic upgrade head
alembic revision --autogenerate -m "description"
pytest tests/ -v

# Frontend
cd frontend && npm run dev
cd frontend && npm run build

# Docker
docker compose up -d
docker compose logs -f predarb
```

## Code conventions

- Python: Use `ruff` for linting, `ruff format` for formatting. Type hints everywhere. Async by default.
- All timestamps UTC. Use `datetime.now(UTC)` not `datetime.utcnow()`.
- Pydantic v2 for all schemas. SQLAlchemy 2.0 style with `mapped_column`.
- Collectors must extend `BaseCollector` and implement `fetch_markets()` and `fetch_prices()`.
- Every API route in `backend/api/routes/` — keep FastAPI router per domain.
- Frontend: Functional components only, hooks for state, TanStack Query for server state.
- Environment variables via `.env` file, loaded by Pydantic `BaseSettings`.

## Platform API quick reference

| Platform | Markets endpoint | Auth needed? | Price format |
|---|---|---|---|
| Polymarket Gamma | `GET https://gamma-api.polymarket.com/markets` | No | 0-1 float |
| Polymarket CLOB | `GET https://clob.polymarket.com/price` | No (read) | 0-1 float |
| Kalshi | `GET https://api.elections.kalshi.com/trade-api/v2/markets` | No | cents → use `_dollars` fields |
| PredictIt | `GET https://www.predictit.org/api/marketdata/all` | No | 0-1 float |
| Manifold | `GET https://api.manifold.markets/v0/markets` | No | 0-1 probability |

## Important gotchas

1. Kalshi is removing legacy integer price fields on March 12, 2026 — use `_dollars` and `_fp` fields only.
2. Polymarket binary markets have two token IDs (YES and NO) — fetch both orderbooks.
3. PredictIt has 10% profit fee + 5% withdrawal fee — arbs need >16% gross to be profitable.
4. Always check liquidity depth, not just midpoint prices.
5. Match markets by semantic meaning, not just title similarity — close dates and resolution criteria matter.
6. Discord webhook rate limit: 30 requests per 60 seconds per webhook URL.

## Environment variables

Copy `.env.example` to `.env` and fill in:
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string  
- `DISCORD_WEBHOOK_URL` — Discord webhook URL for alerts (tier shown in message)
- `KALSHI_API_KEY`, `KALSHI_API_SECRET` — Only needed for trading (Phase 4)
- `POLYMARKET_PRIVATE_KEY` — Only needed for trading (Phase 4)

## Development phases

We're building in phases. See PRD.md §14 for the full plan. Start with Phase 1:
1. Collectors (Polymarket, Kalshi, PredictIt)
2. Normalized market storage
3. Basic fuzzy matching
4. Cross-platform arb detection with fees
5. Discord alerts
6. FastAPI JSON API