"""Lightweight schema migration for SQLite/PostgreSQL development installs.

The project intentionally avoids destructive migrations. Missing listing columns are
added on startup before SQLAlchemy queries use them.
"""
from sqlalchemy import text
from app.db import engine

_COLUMNS = {
    "fingerprint": "VARCHAR(64) DEFAULT ''",
    "duplicate_key": "VARCHAR(64) DEFAULT ''",
    "model": "VARCHAR(255) DEFAULT ''",
    "condition": "VARCHAR(32) DEFAULT 'unknown'",
    "storage_gb": "DOUBLE PRECISION",
    "memory_gb": "DOUBLE PRECISION",
}

_INDEXES = {
    "ix_listings_source_last_seen": "CREATE INDEX IF NOT EXISTS ix_listings_source_last_seen ON listings (source, last_seen_at)",
    "ix_listings_model_condition": "CREATE INDEX IF NOT EXISTS ix_listings_model_condition ON listings (model, condition)",
    "ix_listings_price": "CREATE INDEX IF NOT EXISTS ix_listings_price ON listings (price)",
    "ix_price_history_listing_observed": "CREATE INDEX IF NOT EXISTS ix_price_history_listing_observed ON price_history (listing_id, observed_at)",
}


async def ensure_listing_columns() -> None:
    async with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect == "sqlite":
            rows = await conn.execute(text("PRAGMA table_info(listings)"))
            existing = {row[1] for row in rows.fetchall()}
        else:
            rows = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='listings'"
            ))
            existing = {row[0] for row in rows.fetchall()}

        for name, ddl in _COLUMNS.items():
            if name not in existing:
                await conn.execute(text(f"ALTER TABLE listings ADD COLUMN {name} {ddl}"))

        for ddl in _INDEXES.values():
            await conn.execute(text(ddl))
