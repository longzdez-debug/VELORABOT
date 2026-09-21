# VELORA on blitz.cloud

blitz.cloud can build public GitHub projects and run several apps from one repository. The free beta currently provides 15 apps, 2 GB shared reserved memory, 10 GB storage and one managed database.

## Recommended apps

Create these apps from the same repository:

1. velora-api — Dockerfile: apps/api/Dockerfile — public HTTP app on port 8080. Attach PostgreSQL.
2. velora-miniapp — Dockerfile: apps/miniapp/Dockerfile — public HTTP app on port 8080.
3. velora-http-collector — Dockerfile: apps/http-collector/Dockerfile — enable Runs in the background.
4. velora-browser-collector — Dockerfile: apps/browser-collector/Dockerfile — enable Runs in the background.

The Telegram bot runs inside the API process.

## Environment

API:
DATABASE_URL=<injected by blitz.cloud PostgreSQL>
REDIS_URL=<optional external Redis URL>
TELEGRAM_BOT_TOKEN=<BotFather token>
MINIAPP_URL=https://<your-miniapp>.blitz.cloud
API_PUBLIC_URL=https://<your-api>.blitz.cloud
COLLECTOR_INTERVAL_MS=1500
RUST_LOG=info
COLLECTOR_TOKEN=<long random secret>

Both collectors:
API_PUBLIC_URL=https://<your-api>.blitz.cloud
COLLECTOR_TOKEN=<same secret as API>
COLLECTOR_INTERVAL_MS=1500

Mini App build:
VITE_API_URL=https://<your-api>.blitz.cloud

VITE_API_URL is read at build time, so set it before building/rebuilding the Mini App.

## Important Redis note

The normal VELORA Compose deployment uses Redis for ingest locks, short-lived fingerprint deduplication and market hot-cache. The blitz.cloud free plan currently provides one managed database, so PostgreSQL and Redis cannot simply be created as two free managed databases on the same account. Keep Redis external for the full current behavior, or add a dedicated single-instance fallback before running without Redis.

## Deployment order

1. Create the PostgreSQL database and deploy velora-api.
2. Add the API environment variables and restart.
3. Deploy both collectors as background apps pointing at the API URL.
4. Deploy the Mini App with VITE_API_URL set to the API URL.
5. Set MINIAPP_URL on the API to the Mini App URL and restart.
6. Open the Telegram bot and send /start.

## Free-tier caveats

- The GitHub repository must be public with the current blitz.cloud workflow.
- Docker apps run as uid 1000 and must not require root.
- Browser Collector is the heaviest component; keep its monitor count conservative on the free tier.
