# Blitz deployment — reliable VELORA layout

The repository stays monolithic for local development, but production is split into independent Blitz apps.

## App 1 — VELORA Core

Create a Blitz app from:
- GitHub: longzdez-debug/VELORABOT
- branch: main

Configure two web parts:
- `/` → Mini App → Dockerfile `apps/miniapp/Dockerfile`
- `/api` → API → Dockerfile `apps/api/Dockerfile`

Attach PostgreSQL database:
- `VeloraBD`

Core environment:
- `DATABASE_URL`: use the database value supplied by Blitz; do not hard-code it.
- `TELEGRAM_BOT_TOKEN`: BotFather token.
- `MINIAPP_URL`: the public Core app address.
- `API_PUBLIC_URL`: the public Core API address.
- `COLLECTOR_INTERVAL_MS=1500`
- `COLLECTOR_TOKEN`: long random shared secret.
- `RUST_LOG=info`

Do not add Redis to the Core deployment.

## App 2 — VELORA HTTP Collector

Create a second Blitz app from the same repository and branch.

Configure one background process:
- Dockerfile: `apps/http-collector/Dockerfile`

Environment:
- `API_PUBLIC_URL=https://<CORE-APP-API-ADDRESS>`
- `COLLECTOR_TOKEN=<same secret as Core>`
- `COLLECTOR_INTERVAL_MS=1500`

No PostgreSQL database is attached to this app.
No Telegram token is required.

## App 3 — VELORA Browser Collector

Create a third Blitz app from the same repository and branch.

Configure one background process:
- Dockerfile: `apps/browser-collector/Dockerfile`

Environment:
- `API_PUBLIC_URL=https://<CORE-APP-API-ADDRESS>`
- `COLLECTOR_TOKEN=<same secret as Core>`
- `COLLECTOR_INTERVAL_MS=1500`
- `CHROMIUM_PATH=/usr/bin/chromium`

No PostgreSQL database is attached to this app.
No Telegram token is required.

## Startup order

1. Deploy Core.
2. Confirm Core API is online and PostgreSQL migrations complete.
3. Copy the Core API public address into both collector apps.
4. Deploy HTTP Collector.
5. Deploy Browser Collector.
6. Confirm collector heartbeat appears in Core.
7. Set the Mini App URL used by the Telegram bot to the Core public Mini App address.
8. Open the bot and launch the Mini App.

## Failure isolation

- Browser Collector can restart without taking API or Mini App offline.
- HTTP Collector can restart without taking API or Mini App offline.
- Collector failures do not erase PostgreSQL state.
- PostgreSQL remains attached only to Core.
- Durable notification queue and deduplication remain in PostgreSQL.

## Important

The old four-part single Blitz app should not be repeatedly rebuilt. Once the new Core app is online, the old VELORABOT deployment can be stopped/retired after verification.
