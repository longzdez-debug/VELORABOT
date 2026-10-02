# VELORA

VELORA is a market-intelligence platform for resellers: the Telegram Bot is the radar, while the Telegram Mini App is the terminal.

## Stack

- **TypeScript** — Mini App UI and frontend contracts.
- **Python** — FastAPI, Telegram bot, market/deal intelligence and AI-facing services.
- **Rust** — high-throughput collector/event-processing foundation.
- **PostgreSQL** — source-of-truth listings and alerts.
- **Redis** — realtime queues/cache.
- **C++** and **C#/.NET** are reserved for measured native or Windows-specific components instead of adding complexity without a concrete need.

## Current pipeline

SOURCE -> COLLECTOR -> NORMALIZE -> DEDUP -> MARKET -> DEAL SCORE -> ALERT -> TELEGRAM / MINI APP

The collector accepts a configurable public source URL and extracts structured Product/Offer JSON-LD. Source adapters remain modular so additional permitted sources can be added independently.

## Listing data

The complete original listing description is stored in **description_raw** and is searchable. Derived AI/semantic signals are separate and never replace source text.

## API

- GET /health
- GET /api/stats
- GET /api/listings?q=...
- GET /api/listings/{id}
- GET /api/alerts?user_id=...
- POST /api/alerts?user_id=...
- DELETE /api/alerts/{id}?user_id=...
- POST /api/profit

## Run

Copy `.env.example` to `.env`. For Docker, the default example points at the compose PostgreSQL/Redis services. A Telegram bot token and public Mini App URL are only required when Telegram integration is enabled.

```bash
docker compose up --build
```

The web terminal is served on port 8000.

## Safety / data acquisition

VELORA is designed around permitted public sources and official integrations where available. It does not require authentication bypass, CAPTCHA bypass, stolen cookies or access to private infrastructure.
