from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from app.config import settings


@dataclass(frozen=True)
class ListingEvent:
    event_id: str
    event_type: str
    listing_id: int
    source: str
    source_id: str
    detected_at_ms: int
    price: float | None = None

    def to_fields(self) -> dict[str, str]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "listing_id": str(self.listing_id),
            "source": self.source,
            "source_id": self.source_id,
            "detected_at_ms": str(self.detected_at_ms),
            "price": "" if self.price is None else str(self.price),
        }

    @classmethod
    def from_fields(cls, fields: dict[str, Any]) -> "ListingEvent":
        return cls(
            event_id=str(fields["event_id"]),
            event_type=str(fields["event_type"]),
            listing_id=int(fields["listing_id"]),
            source=str(fields["source"]),
            source_id=str(fields["source_id"]),
            detected_at_ms=int(fields["detected_at_ms"]),
            price=float(fields["price"]) if fields.get("price") not in (None, "") else None,
        )


def new_listing_event(event_type: str, listing_id: int, source: str, source_id: str, price: float | None = None) -> ListingEvent:
    return ListingEvent(uuid.uuid4().hex, event_type, listing_id, source, source_id, time.time_ns() // 1_000_000, price)


class EventBus:
    """Transport-neutral stream contract; Redis can later be swapped for Kafka."""

    def __init__(self, redis_url: str):
        self.redis: Redis = Redis.from_url(redis_url, decode_responses=True)

    async def ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(settings.event_stream, settings.event_consumer_group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish(self, event: ListingEvent) -> str:
        return str(await self.redis.xadd(settings.event_stream, event.to_fields(), maxlen=settings.event_maxlen, approximate=True))

    async def consume(self, consumer: str, count: int = 20, block_ms: int = 1000):
        await self.ensure_group()
        return await self.redis.xreadgroup(settings.event_consumer_group, consumer, {settings.event_stream: ">"}, count=count, block=block_ms)

    async def claim_stale(self, consumer: str, min_idle_ms: int = 30_000, count: int = 20):
        await self.ensure_group()
        result = await self.redis.xautoclaim(settings.event_stream, settings.event_consumer_group, consumer, min_idle_time=min_idle_ms, start_id="0-0", count=count)
        return result[1] if result else []

    async def ack(self, message_id: str) -> None:
        await self.redis.xack(settings.event_stream, settings.event_consumer_group, message_id)

    async def dead_letter(self, message_id: str, event: ListingEvent, error: str) -> str:
        return str(await self.redis.xadd(settings.event_dead_stream, {**event.to_fields(), "failed_message_id": message_id, "error": error[:1000]}, maxlen=10_000, approximate=True))

    async def close(self) -> None:
        await self.redis.aclose()


def event_json(event: ListingEvent) -> str:
    return json.dumps(event.to_fields(), ensure_ascii=False, separators=(",", ":"))