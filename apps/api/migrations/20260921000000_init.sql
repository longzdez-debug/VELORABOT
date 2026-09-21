CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS users(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),telegram_id bigint UNIQUE NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS monitors(id uuid PRIMARY KEY,user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,url text NOT NULL,name text,enabled boolean NOT NULL DEFAULT true,interval_ms bigint NOT NULL DEFAULT 1500,notify_new boolean NOT NULL DEFAULT true,notify_price_drop boolean NOT NULL DEFAULT true,notify_below_market boolean NOT NULL DEFAULT true,min_drop_byn double precision NOT NULL DEFAULT 50,min_drop_percent double precision NOT NULL DEFAULT 3,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS listings(id uuid PRIMARY KEY,kufar_id text UNIQUE NOT NULL,url text NOT NULL,title text NOT NULL,description text,price double precision,currency text NOT NULL DEFAULT 'BYN',location text,images text[] NOT NULL DEFAULT '{}',published_at timestamptz,first_seen_at timestamptz NOT NULL,last_seen_at timestamptz NOT NULL,market_price double precision,market_confidence double precision,status text NOT NULL DEFAULT 'active',created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS monitor_listings(monitor_id uuid NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,listing_id uuid NOT NULL REFERENCES listings(id) ON DELETE CASCADE,PRIMARY KEY(monitor_id,listing_id));
CREATE TABLE IF NOT EXISTS price_history(id bigserial PRIMARY KEY,listing_id uuid NOT NULL REFERENCES listings(id) ON DELETE CASCADE,price double precision NOT NULL,observed_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_monitors_enabled ON monitors(enabled);
CREATE INDEX IF NOT EXISTS idx_listings_seen ON listings(first_seen_at DESC);
CREATE TABLE IF NOT EXISTS notifications(
 id bigserial PRIMARY KEY,
 user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 monitor_id uuid REFERENCES monitors(id) ON DELETE SET NULL,
 listing_id uuid NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
 kind text NOT NULL,
 sent_at timestamptz NOT NULL DEFAULT now(),
 telegram_message_id bigint,
 detection_latency_ms bigint,
 delivery_latency_ms bigint,
 total_latency_ms bigint,
 UNIQUE(user_id,listing_id,kind)
);
CREATE INDEX IF NOT EXISTS idx_price_history_listing_observed ON price_history(listing_id,observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_listings_market ON listings(status,price);
