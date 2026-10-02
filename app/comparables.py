from __future__ import annotations

import re
from sqlalchemy import select, or_
from app.attributes import extract_attributes
from app.db import Listing


def _tokens(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[\\w]+", text.casefold())
        if len(t) >= 3 and not t.isdigit()
    }


def comparable_score(source: Listing, candidate: Listing) -> int:
    title_tokens = _tokens(source.title)
    candidate_tokens = _tokens(candidate.title)
    overlap = len(title_tokens & candidate_tokens)
    score = min(35, overlap * 7)

    if source.model and candidate.model and source.model.casefold() == candidate.model.casefold():
        score += 35

    if source.storage_gb and candidate.storage_gb:
        if float(source.storage_gb) == float(candidate.storage_gb):
            score += 12
        else:
            score -= 8

    if source.memory_gb and candidate.memory_gb:
        if float(source.memory_gb) == float(candidate.memory_gb):
            score += 8
        else:
            score -= 5

    if source.condition != "unknown" and candidate.condition != "unknown":
        if source.condition == candidate.condition:
            score += 8
        elif {source.condition, candidate.condition} <= {"new", "excellent", "good"}:
            score += 2
        else:
            score -= 6

    return max(0, min(100, score))


async def comparable_listings(session, source: Listing, limit: int = 500) -> list[Listing]:
    # Prefer normalized attributes, but fall back to title/description overlap.
    model = (source.model or "").strip()
    terms = list(_tokens(source.title))[:6]
    conditions = []
    if model:
        conditions.append(Listing.model.ilike(model))
    if terms:
        conditions.extend(
            or_(Listing.title.ilike(f"%{t}%"), Listing.description_raw.ilike(f"%{t}%"))
            for t in terms
        )
    if not conditions:
        return []

    stmt = (
        select(Listing)
        .where(Listing.id != source.id, Listing.price > 0, or_(*conditions))
        .order_by(Listing.last_seen_at.desc())
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars().all())

    # If normalized model is missing on older rows, enrich only for comparison.
    if model:
        src_attr = extract_attributes(source.title, source.description_raw)
    else:
        src_attr = None

    scored: list[tuple[int, Listing]] = []
    for row in rows:
        if not row.model and src_attr and src_attr.model:
            row_model = extract_attributes(row.title, row.description_raw).model
            if row_model:
                score = comparable_score(source, row)
                if row_model.casefold() == src_attr.model.casefold():
                    score += 25
            else:
                score = comparable_score(source, row)
        else:
            score = comparable_score(source, row)
        if score >= 25:
            scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored]


async def comparable_prices(session, source: Listing, limit: int = 500) -> list[float]:
    rows = await comparable_listings(session, source, limit=limit)
    return [float(row.price) for row in rows if row.price and row.price > 0]
