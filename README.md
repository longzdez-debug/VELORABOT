# VELORA

VELORA is a Telegram-first Kufar.by monitoring platform for resellers.

## Architecture

- Core API: Rust + Axum + SQLx + PostgreSQL.
- Telegram bot: runs inside the Core API process.
- Market engine: PostgreSQL-backed weighted matching, outlier filtering and confidence scoring.
- Notification queue: durable PostgreSQL queue with retries.
- HTTP collector: lightweight Node.js collector for direct/page-based acquisition.
- Browser collector: isolated Node.js + Playwright + system Chromium collector.
- Mini App: React + TypeScript + Vite Telegram Mini App.
- No Redis dependency is required for production.

Collectors are isolated from the Core API so a browser/runtime failure cannot take the main application offline.

## Local development

1. Copy .env.example to .env.
2. Fill TELEGRAM_BOT_TOKEN and COLLECTOR_TOKEN.
3. Run: docker compose up --build

## Blitz deployment

For reliable deployment, do not deploy all four processes as one Blitz build.

Use three Blitz apps from this same public GitHub repository:

1. VELORA Core
   - Mini App (/, Dockerfile: apps/miniapp/Dockerfile)
   - API (/api, Dockerfile: apps/api/Dockerfile)
   - One attached PostgreSQL database: VeloraBD
2. VELORA HTTP Collector
   - Background process from apps/http-collector/Dockerfile
3. VELORA Browser Collector
   - Background process from apps/browser-collector/Dockerfile

The Core app is the only app that needs the database and Telegram bot token. Collectors only need API_PUBLIC_URL, COLLECTOR_TOKEN and COLLECTOR_INTERVAL_MS.

See docs/blitz-deployment.md for the exact setup order and environment variables.
