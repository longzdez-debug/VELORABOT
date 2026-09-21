ALTER TABLE listings
  ADD COLUMN IF NOT EXISTS stale_since timestamptz,
  ADD COLUMN IF NOT EXISTS removed_at timestamptz,
  ADD COLUMN IF NOT EXISTS relisted_from_listing_id uuid REFERENCES listings(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS normalized_fingerprint text;

CREATE INDEX IF NOT EXISTS idx_listings_status_seen ON listings(status,last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_listings_relisted_from ON listings(relisted_from_listing_id);
CREATE INDEX IF NOT EXISTS idx_listings_fingerprint ON listings(normalized_fingerprint);

CREATE TABLE IF NOT EXISTS monitor_collector_state(
  monitor_id uuid NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
  collector text NOT NULL,
  last_success_at timestamptz NOT NULL,
  last_listing_count integer NOT NULL DEFAULT 0,
  observed_kufar_ids text[] NOT NULL DEFAULT '{}',
  PRIMARY KEY(monitor_id,collector)
);
CREATE INDEX IF NOT EXISTS idx_monitor_collector_state_success ON monitor_collector_state(last_success_at DESC);

CREATE TABLE IF NOT EXISTS listing_status_history(
  id bigserial PRIMARY KEY,
  listing_id uuid NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  from_status text,
  to_status text NOT NULL,
  reason text NOT NULL,
  changed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_listing_status_history_listing ON listing_status_history(listing_id,changed_at DESC);
