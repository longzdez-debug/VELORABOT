from __future__ import annotations

import hashlib
import re

from sqlalchemy import or_, select

from app.db import Listing, Session


def normalize_text(value: str) -> str:
    value = value.casefold().replace("ё", "е")
    return " ".join(re.findall(r"[\w]+", value))


def duplicate_key_for(
    title: str,
    model: str = "",
    storage_gb: float | None = None,
    image_url: str = "",
) -> str:
    raw = "|".join(
        (
            normalize_text(title),
            normalize_text(model),
            str(storage_gb or ""),
            image_url.strip().casefold(),
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def fingerprint_for(
    title: str,
    description: str,
    seller: str,
    image_url: str = "",
) -> str:
    title_tokens = sorted(set(normalize_text(title).split()))
    body = normalize_text(description)[:1000]
    seller_norm = normalize_text(seller)
    image = image_url.strip().casefold()
    raw = "|".join((" ".join(title_tokens), body, seller_norm, image))
    return hashlib.sha256(raw.encode()).hexdigest()


async def duplicate_candidates(listing_id: int, limit: int = 20) -> list[dict]:
    async with Session() as s:
        listing = await s.get(Listing, listing_id)
        if not listing:
            return []

        exact: list[Listing] = []
        if listing.duplicate_key:
            exact = list(
                (
                    await s.execute(
                        select(Listing)
                        .where(
                            Listing.id != listing_id,
                            Listing.duplicate_key == listing.duplicate_key,
                        )
                        .limit(limit)
                    )
                ).scalars().all()
            )

        tokens = sorted(set(normalize_text(listing.title).split()))[:8]
        conditions = [
            or_(
                Listing.title.ilike(f"%{token}%"),
                Listing.description_raw.ilike(f"%{token}%"),
            )
            for token in tokens
            if len(token) >= 3
        ]

        rows = exact
        if conditions:
            rows += list(
                (
                    await s.execute(
                        select(Listing)
                        .where(Listing.id != listing_id, *conditions)
                        .limit(limit)
                    )
                ).scalars().all()
            )

        unique_rows: list[Listing] = []
        seen_ids: set[int] = set()
        for row in rows:
            if row.id not in seen_ids:
                seen_ids.add(row.id)
                unique_rows.append(row)

    result = []
    source_key = normalize_text(listing.title)
    for row in unique_rows:
        candidate_key = normalize_text(row.title)
        overlap = len(set(source_key.split()) & set(candidate_key.split()))
        score = min(
            100,
            overlap * 18 + (25 if row.model and row.model == listing.model else 0),
        )
        if (
            listing.duplicate_key
            and row.duplicate_key
            and listing.duplicate_key == row.duplicate_key
        ):
            score += 45
        if row.seller and listing.seller and normalize_text(row.seller) == normalize_text(listing.seller):
            score += 20
        if row.image_url and listing.image_url and row.image_url == listing.image_url:
            score += 35
        if score >= 45:
            result.append(
                {
                    "id": row.id,
                    "source": row.source,
                    "title": row.title,
                    "price": row.price,
                    "url": row.url,
                    "similarity": min(100, score),
                }
            )
    return sorted(result, key=lambda x: x["similarity"], reverse=True)
