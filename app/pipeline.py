from __future__ import annotations

import asyncio
import logging
import os
import socket
import time

from app.config import settings
from app.db import Session, Listing
from app.events import EventBus, ListingEvent
from app.notify import evaluate_and_notify

log = logging.getLogger(__name__)


def _consumer_name() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


async def publish_listing_event(event: ListingEvent) -> None:
    bus = EventBus(settings.redis_url)
    try:
        await bus.publish(event)
    finally:
        await bus.close()


async def _process(bus: EventBus, message_id: str, fields: dict[str, str]) -> None:
    event = ListingEvent.from_fields(fields)
    started = time.time_ns() // 1_000_000
    try:
        async with Session() as session:
            if not await session.get(Listing, event.listing_id):
                await bus.ack(message_id)
                return
        await evaluate_and_notify(event.listing_id, event.event_type)
        await bus.ack(message_id)
        now = time.time_ns() // 1_000_000
        log.info(
            "event processed id=%s type=%s listing=%s processing_ms=%s total_ms=%s",
            event.event_id,
            event.event_type,
            event.listing_id,
            max(0, now - started),
            max(0, now - event.detected_at_ms),
        )
    except Exception:
        log.exception("event processing failed message=%s", message_id)
        # Leave pending; a later worker can reclaim it.


async def notification_worker() -> None:
    consumer = _consumer_name()
    while True:
        bus = EventBus(settings.redis_url)
        try:
            await bus.ensure_group()
            log.info(
                "event worker online consumer=%s stream=%s group=%s",
                consumer,
                settings.event_stream,
                settings.event_consumer_group,
            )
            while True:
                for message_id, fields in await bus.claim_stale(consumer):
                    await _process(bus, message_id, fields)

                rows = await bus.consume(
                    consumer,
                    count=settings.event_batch_size,
                    block_ms=1000,
                )
                for _, messages in rows:
                    for message_id, fields in messages:
                        await _process(bus, message_id, fields)
        except asyncio.CancelledError:
            await bus.close()
            raise
        except Exception:
            log.exception("event bus unavailable; retrying")
            await bus.close()
            await asyncio.sleep(settings.event_reconnect_seconds)


async def run_event_worker() -> None:
    await notification_worker()
