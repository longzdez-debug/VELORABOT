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
ALTER TABLE listings ADD COLUMN IF NOT EXISTS first_detected_at timestamptz;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS telegram_sent_at timestamptz;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS detection_latency_ms bigint;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS delivery_latency_ms bigint;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS total_latency_ms bigint;
