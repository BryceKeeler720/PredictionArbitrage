# PredArb — Prediction Market Arbitrage Scanner

Self-hosted tool that scans Polymarket, Kalshi, PredictIt, and Manifold for cross-platform arbitrage opportunities and alerts you via Discord.

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your Discord webhook URLs

# 2. Run with Docker Compose
docker compose up -d

# 3. Access dashboard
open http://localhost:8420
```

## What it does

PredArb continuously polls prediction market APIs, normalizes the data into a unified format, fuzzy-matches equivalent markets across platforms, and calculates fee-adjusted arbitrage profit. When an opportunity exceeds your configured thresholds, it fires a Discord webhook with full details.

**Example:** If Polymarket prices "Will X happen?" at YES $0.42 and Kalshi prices the same event at NO $0.52, you can buy both for $0.94 and guarantee a $1.00 payout — a 6.4% risk-free return (before fees).

## Supported Platforms

| Platform | Data Access | Fee Impact |
|---|---|---|
| Polymarket | Public REST + CLOB APIs | ~2% taker fee |
| Kalshi | Public REST API | ~2% per contract |
| PredictIt | Public REST API | 10% profit + 5% withdrawal (~16% drag) |
| Manifold | Public REST API | Play money — signal only |

## Project Structure

```
predarb/
├── CLAUDE.md              # Claude Code project context
├── docs/PRD.md            # Full product requirements
├── skill/SKILL.md         # Claude Code skill file
├── backend/               # FastAPI + collectors + arb engine
├── frontend/              # React + Tailwind dashboard
├── docker-compose.yml     # Homelab deployment
├── pyproject.toml         # Python dependencies
└── .env.example           # Environment template
```

## Development

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn backend.main:app --reload --port 8420

# Frontend
cd frontend && npm install && npm run dev
```

## Building with Claude Code

This project is designed to be built iteratively with Claude Code. The `CLAUDE.md` file provides project context, and the `skill/SKILL.md` file can be installed as a Claude Code skill for ongoing development.

```bash
# Install the skill (from project root)
# Drop prediction-arb.skill into your Claude Code skills directory
```

Start by asking Claude Code to implement Phase 1 from the PRD:
> "Read CLAUDE.md and docs/PRD.md, then implement the Polymarket collector following the patterns in skill/SKILL.md"

## License

MIT