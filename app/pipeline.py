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


async def notification_worker() -> None:
    """Consume listing events without blocking collectors on Telegram.

    Redis outages are treated as transient. The worker reconnects instead of
    bringing down the API/collectors.
    """
    consumer = _consumer_name()
    while True:
        bus = EventBus(settings.redis_url)
        try:
            await bus.ensure_group()
            log.info("event worker online consumer=%s stream=%s", consumer, bus.stream)
            while True:
                rows = await bus.consume(consumer, count=settings.event_batch_size, block_ms=1000)
                if not rows:
                    continue
                for _, messages in rows:
                    for message_id, fields in messages:
                        event = ListingEvent.from_fields(fields)
                        started = time.time_ns() // 1_000_000
                        try:
                            # Ensure the listing still exists before evaluating.
                            async with Session() as session:
                                if not await session.get(Listing, event.listing_id):
                                    await bus.ack(message_id)
                                    continue
                            await evaluate_and_notify(event.listing_id, event.event_type)
                            await bus.ack(message_id)
                            log.info(
                                "event processed id=%s type=%s listing=%s latency_ms=%s",
                                event.event_id,
                                event.event_type,
                                event.listing_id,
                                max(0, started - event.detected_at_ms),
                            )
                        except Exception:
                            log.exception("event processing failed message=%s", message_id)
                            # Do not ACK. Redis keeps the message pending so a
                            # recovery worker can claim/retry it.
        except asyncio.CancelledError:
            await bus.close()
            raise
        except Exception:
            log.exception("event bus unavailable; retrying")
            await bus.close()
            await asyncio.sleep(settings.event_reconnect_seconds)


async def run_event_worker() -> None:
    await notification_worker()
