# VELORA

VELORA is a Telegram-first Kufar.by monitoring platform for resellers.

Architecture:
- Rust API: Axum + SQLx + PostgreSQL
- Telegram bot: teloxide
- Browser collector: Node.js + Playwright
- Redis for deduplication and hot state
- React + TypeScript + Vite Telegram Mini App
- Docker Compose

The system uses short-interval collectors instead of minute cron jobs. Kufar can change its frontend, so browser/network collection is isolated from the product API.

Quick start:
1. Copy .env.example to .env.
2. Fill TELEGRAM_BOT_TOKEN and MINIAPP_URL.
3. Run docker compose up --build.
