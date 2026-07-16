"""Kafka consumer for banking events with enrichment pipeline."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Callable

import structlog
from confluent_kafka import Consumer, KafkaError, KafkaException

from sentinel_swarm.config import get_settings
from sentinel_swarm.ingestion.enrichment import EnrichmentPipeline
from sentinel_swarm.models.events import BankingEvent, EnrichedEvent

logger = structlog.get_logger("ingestion.consumer")


class EventConsumer:
    """Consumes banking events from Kafka, enriches them, and forwards to processing."""

    def __init__(
        self,
        on_event: Callable[[EnrichedEvent], None] | None = None,
    ) -> None:
        settings = get_settings()
        self._conf = {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_consumer_group,
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
            "max.poll.interval.ms": 30_000,
        }
        self._topic = settings.kafka_topic_events
        self._consumer: Consumer | None = None
        self._enrichment = EnrichmentPipeline()
        self._on_event = on_event
        self._running = False

    def start(self) -> None:
        """Start consuming events (blocking)."""
        self._consumer = Consumer(self._conf)
        self._consumer.subscribe([self._topic])
        self._running = True
        logger.info("consumer_started", topic=self._topic)

        try:
            while self._running:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    self._handle_error(msg.error())
                    continue
                self._process_message(msg)
        except KeyboardInterrupt:
            logger.info("consumer_interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        """Gracefully stop the consumer."""
        self._running = False
        if self._consumer:
            self._consumer.close()
            logger.info("consumer_stopped")

    def _process_message(self, msg) -> None:
        """Parse, enrich, and forward a single Kafka message."""
        start = time.monotonic()
        try:
            raw = json.loads(msg.value().decode("utf-8"))
            event = BankingEvent.model_validate(raw)
            logger.info(
                "event_received",
                event_id=event.event_id,
                event_type=event.event_type,
                account_id=event.account_id,
            )

            enriched = self._enrichment.enrich(event)
            enriched.enrichment_latency_ms = int((time.monotonic() - start) * 1000)

            if self._on_event:
                self._on_event(enriched)

            logger.info(
                "event_enriched",
                event_id=event.event_id,
                latency_ms=enriched.enrichment_latency_ms,
            )
        except json.JSONDecodeError:
            logger.error("invalid_json", raw=msg.value()[:200])
        except Exception as e:
            logger.error("processing_error", error=str(e), exc_info=True)

    def _handle_error(self, error: KafkaError) -> None:
        if error.code() == KafkaError._PARTITION_EOF:
            return  # Normal — end of partition
        logger.error("kafka_error", code=error.code(), reason=error.str())
        if error.fatal():
            raise KafkaException(error)


class AsyncEventConsumer:
    """Async wrapper around EventConsumer for use with asyncio pipelines."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[EnrichedEvent] = asyncio.Queue(maxsize=1000)
        self._consumer = EventConsumer(on_event=self._enqueue)
        self._task: asyncio.Task | None = None

    def _enqueue(self, event: EnrichedEvent) -> None:
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("event_queue_full", dropping=event.event.event_id)

    async def start(self) -> None:
        """Start consumer in a background thread."""
        loop = asyncio.get_running_loop()
        self._task = asyncio.create_task(
            loop.run_in_executor(None, self._consumer.start)
        )

    async def stop(self) -> None:
        self._consumer.stop()
        if self._task:
            self._task.cancel()

    async def get_event(self, timeout: float = 5.0) -> EnrichedEvent | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
