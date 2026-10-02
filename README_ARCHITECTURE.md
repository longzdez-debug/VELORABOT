# VELORA Architecture

VELORA is intentionally polyglot by responsibility.

- TypeScript: Telegram Mini App UI and frontend contracts.
- Python: FastAPI, Telegram bot, market intelligence and AI-facing services.
- Rust: high-throughput collector/event-processing foundation.
- C++: reserved for measured native hotspots such as image processing/inference.
- C#/.NET: reserved for a Windows/desktop agent if the product needs one.

## Data rule
description_raw is immutable source data. AI-derived fields never replace it. Search covers title and full original description.

## Event path
SOURCE -> COLLECTOR -> NORMALIZE -> DEDUP -> MARKET -> DEAL SCORE -> ALERT -> TELEGRAM / MINI APP

The collector layer is adapter-based so permitted public sources can be added without coupling the domain to one marketplace.
