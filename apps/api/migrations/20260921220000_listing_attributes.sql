ALTER TABLE listings ADD COLUMN IF NOT EXISTS attributes jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS idx_listings_attributes_gin ON listings USING gin (attributes);
