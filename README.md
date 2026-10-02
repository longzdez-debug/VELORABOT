# VELORA

VELORA is a market-intelligence platform for resellers: Telegram Bot = radar, Telegram Mini App = terminal.

## Fast KUFAR radar

VELORA has a dedicated KUFAR collector in addition to the generic public-page collector. It uses the public search JSON endpoint currently used by the KUFAR web client, polls the newest page of every configured query in parallel, deduplicates by KUFAR ad_id, records price history, and emits NEW / PRICE_CHANGED / UPDATED events.

Configure:
    KUFAR_QUERIES=iphone 15 pro,rtx 4070,macbook m2
    KUFAR_INTERVAL_MS=1000
    KUFAR_SIZE=42

The adapter intentionally polls only explicit searches rather than crawling the whole marketplace. This keeps latency and request volume bounded. The search response can contain ad_id, subject, price_byn, body, ad_link, images and list_time. The adapter preserves the original body as description_raw.

## Acquisition

VELORA is source-agnostic. Generic acquisition supports public HTML + JSON-LD. KUFAR has a dedicated fast JSON adapter. No private authentication, CAPTCHA bypass or stolen sessions are used.

## Core flow

KUFAR SEARCH JSON / PUBLIC PAGE -> NORMALIZE -> DEDUP -> EVENT -> MARKET/DEAL -> TELEGRAM / MINI APP

## Important product invariant

The original listing description is source data. AI-derived fields are additional signals and never replace it. Search and deal analysis use the full description_raw.

## Run

Copy .env.example to .env, set TELEGRAM_BOT_TOKEN and KUFAR_QUERIES, then run docker compose up --build.
