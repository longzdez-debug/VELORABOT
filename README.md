# VELORA

Market intelligence and deal discovery platform for resellers.

## Core
- Telegram Bot — notification radar for new and high-value listings.
- Telegram Mini App — primary search, deals, market and listing interface.
- Collector layer — modular marketplace ingestion.
- Market Engine — comparable pricing, market deviation and history.
- Deal Engine — Deal Score, liquidity, risk and profit estimation.
- Description Intelligence — preserve the original listing description and derive searchable signals without replacing source text.

## MVP architecture
Telegram Bot + Mini App -> FastAPI -> PostgreSQL / Redis
Collectors -> event pipeline -> normalization -> market/deal engine -> notifications

## Layout
- apps/api — backend API
- apps/bot — Telegram bot
- apps/web — Mini App
- services/collector — marketplace collectors
- services/market — market intelligence
- services/deals — opportunity scoring
- packages/domain — shared models
- infra — local infrastructure
- tests — automated tests

## Data principle
The original listing description is first-class source data. Store it as description_raw. AI/semantic attributes are derived data and must never silently replace the original text.
