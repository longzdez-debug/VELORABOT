from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis


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


def new_listing_event(
    event_type: str,
    listing_id: int,
    source: str,
    source_id: str,
    price: float | None = None,
) -> ListingEvent:
    return ListingEvent(
        event_id=uuid.uuid4().hex,
        event_type=event_type,
        listing_id=listing_id,
        source=source,
        source_id=source_id,
        detected_at_ms=time.time_ns() // 1_000_000,
        price=price,
    )


class EventBus:
    """Transport-neutral event bus.

    Business logic depends only on publish/consume/ack/retry semantics, so Redis
    Streams can later be replaced by Kafka without changing collectors or workers.
    """

    stream = "velora:listings:events"
    dead_stream = "velora:listings:dead"
    group = "velora-processors"

    def __init__(self, redis_url: str):
        self.redis: Redis = Redis.from_url(redis_url, decode_responses=True)

    async def ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish(self, event: ListingEvent) -> str:
        fields = event.to_fields()
        return str(await self.redis.xadd(self.stream, fields, maxlen=100_000, approximate=True))

    async def consume(self, consumer: str, count: int = 20, block_ms: int = 1000):
        await self.ensure_group()
        rows = await self.redis.xreadgroup(
            self.group, consumer, {self.stream: ">"}, count=count, block=block_ms
        )
        return rows

    async def ack(self, message_id: str) -> None:
        await self.redis.xack(self.stream, self.group, message_id)

    async def retry_or_dead_letter(self, message_id: str, event: ListingEvent, error: str) -> None:
        # Keep retry metadata bounded in the stream payload. A worker can retry
        # transient failures without losing the original event.
        await self.redis.xadd(
            self.dead_stream,
            {
                **event.to_fields(),
                "failed_message_id": message_id,
                "error": error[:1000],
            },
            maxlen=10_000,
            approximate=True,
        )

    async def close(self) -> None:
        await self.redis.aclose()


def event_json(event: ListingEvent) -> str:
    return json.dumps(event.to_fields(), ensure_ascii=False, separators=(",", ":"))
