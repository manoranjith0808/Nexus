"""Kafka producer for sending alerts and test events."""

from __future__ import annotations

import json

import structlog
from confluent_kafka import Producer

from sentinel_swarm.config import get_settings
from sentinel_swarm.models.events import BankingEvent

logger = structlog.get_logger("ingestion.producer")


class EventProducer:
    """Produces banking events to Kafka (for testing and alert forwarding)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._producer = Producer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "client.id": "sentinel-producer",
        })
        self._topic_events = settings.kafka_topic_events
        self._topic_alerts = settings.kafka_topic_alerts

    def send_event(self, event: BankingEvent) -> None:
        """Send a banking event to the events topic."""
        payload = event.model_dump_json()
        self._producer.produce(
            self._topic_events,
            key=event.account_id.encode("utf-8"),
            value=payload.encode("utf-8"),
            callback=self._delivery_callback,
        )
        self._producer.poll(0)

    def send_alert(self, alert: dict) -> None:
        """Send an alert to the alerts topic."""
        payload = json.dumps(alert)
        self._producer.produce(
            self._topic_alerts,
            value=payload.encode("utf-8"),
            callback=self._delivery_callback,
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 5.0) -> None:
        self._producer.flush(timeout)

    @staticmethod
    def _delivery_callback(err, msg) -> None:
        if err:
            logger.error("delivery_failed", error=str(err), topic=msg.topic())
        else:
            logger.debug("delivered", topic=msg.topic(), partition=msg.partition())
