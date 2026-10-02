from __future__ import annotations

import re

from redis.asyncio import Redis

from app.config import settings
from app.db import Alert, Session
from sqlalchemy import select

TOKEN_RE = re.compile(r"[\\w-]{2,}", re.UNICODE)
PREFIX = "velora:alerts:"
ACTIVE_KEY = PREFIX + "active"
TOKEN_PREFIX = PREFIX + "term:"


def terms(query: str) -> set[str]:
    return {x.casefold() for x in TOKEN_RE.findall(query or "")}


class AlertIndex:
    """Redis inverted index for alert matching.

    PostgreSQL remains the source of truth. Redis only narrows candidate alert IDs,
    keeping the event-to-notification path off a full-table scan.
    """

    def __init__(self, redis_url: str | None = None):
        self.redis: Redis = Redis.from_url(
            redis_url or settings.redis_url, decode_responses=True
        )

    async def add(self, alert: Alert) -> None:
        pipe = self.redis.pipeline()
        pipe.sadd(ACTIVE_KEY, alert.id)
        for term in terms(alert.query):
            pipe.sadd(TOKEN_PREFIX + term, alert.id)
        await pipe.execute()

    async def remove(self, alert: Alert) -> None:
        pipe = self.redis.pipeline()
        pipe.srem(ACTIVE_KEY, alert.id)
        for term in terms(alert.query):
            pipe.srem(TOKEN_PREFIX + term, alert.id)
        await pipe.execute()

    async def candidates(self, query: str) -> set[int]:
        query_terms = terms(query)
        if not query_terms:
            raw = await self.redis.smembers(ACTIVE_KEY)
        else:
            keys = [TOKEN_PREFIX + term for term in sorted(query_terms)]
            raw = await self.redis.sinter(*keys)
        return {int(x) for x in raw}

    async def candidates_for_text(self, text: str) -> set[int]:
        """Return alerts sharing at least one indexed token with listing text."""
        keys = [TOKEN_PREFIX + term for term in sorted(terms(text))]
        if not keys:
            return set()
        pipe = self.redis.pipeline()
        for key in keys:
            pipe.smembers(key)
        rows = await pipe.execute()
        result: set[int] = set()
        for row in rows:
            result.update(int(x) for x in row)
        return result

    async def rebuild(self) -> int:
        await self.redis.delete(ACTIVE_KEY)
        async with Session() as session:
            rows = (await session.execute(
                select(Alert).where(Alert.active.is_(True))
            )).scalars().all()
        if not rows:
            return 0
        pipe = self.redis.pipeline()
        for alert in rows:
            pipe.sadd(ACTIVE_KEY, alert.id)
            for term in terms(alert.query):
                pipe.sadd(TOKEN_PREFIX + term, alert.id)
        await pipe.execute()
        return len(rows)

    async def close(self) -> None:
        await self.redis.aclose()
