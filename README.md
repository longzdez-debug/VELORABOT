# VELORA

VELORA is a market-intelligence platform for resellers: Telegram Bot = radar, Telegram Mini App = terminal.

## Architecture

- **TypeScript** — Mini App and frontend contracts.
- **Python** — API, Telegram bot, market/deal intelligence and AI-facing services.
- **Rust** — high-throughput collector/event-processing foundation.
- **PostgreSQL** — listings, price history and alerts.
- **Redis** — realtime queue/cache layer.
- **C++** — reserved for measured native hotspots.
- **C#/.NET** — reserved for an optional Windows/desktop agent.

## Acquisition: API is not a requirement

VELORA is source-agnostic. A source can be integrated through an official API/feed when available, or through permitted public pages.

The current web collector polls one or many configured public pages, fetches normal HTML, extracts JSON-LD Product/Offer data when present, falls back to ordinary HTML listing cards, normalizes title/price/URL/image/location, preserves the complete original description in `description_raw`, deduplicates by URL fingerprint, records price changes, evaluates Deal Score, and evaluates saved alerts for Telegram notifications.

It is not tied to KUFAR. KUFAR is one possible source, while additional marketplaces/catalogs/search pages can be added through adapters. We do not depend on private APIs, authentication bypass, CAPTCHA bypass or stolen sessions.

## Core flow

SOURCE PAGE/API -> COLLECTOR -> NORMALIZE -> DEDUP -> PRICE HISTORY -> MARKET/DEAL -> ALERT -> TELEGRAM / MINI APP

## API

- GET /health
- GET /api/stats
- GET /api/listings?q=...&min_score=...&max_price=...
- GET /api/listings/{id}
- GET /api/alerts?user_id=...
- POST /api/alerts?user_id=...
- DELETE /api/alerts/{id}?user_id=...
- POST /api/profit

## Run

Copy `.env.example` to `.env`, configure one or more permitted public pages in `COLLECTOR_URL` / `COLLECTOR_URLS`, and provide `TELEGRAM_BOT_TOKEN` only if Telegram delivery is wanted.

For Docker:

    docker compose up --build

The Mini App/API is served on port 8000.

## Important product invariant

The original listing description is source data. AI-derived fields are additional signals and never replace it. Search and deal analysis can use the full description.
