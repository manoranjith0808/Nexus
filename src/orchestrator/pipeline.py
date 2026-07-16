"""Main pipeline: connects Kafka consumer → Orchestrator → outputs."""

from __future__ import annotations

import asyncio

import structlog

from sentinel_swarm.config import get_settings
from sentinel_swarm.graph.neo4j_client import Neo4jClient
from sentinel_swarm.ingestion.consumer import AsyncEventConsumer
from sentinel_swarm.models.case import CaseState
from sentinel_swarm.models.events import EnrichedEvent
from sentinel_swarm.orchestrator.graph import SentinelSwarmOrchestrator
from sentinel_swarm.utils.logging import setup_logging

logger = structlog.get_logger("pipeline")


class SentinelSwarmPipeline:
    """End-to-end pipeline: Kafka → Enrichment → Graph → Agent Swarm → Actions."""

    def __init__(self) -> None:
        settings = get_settings()
        setup_logging(settings.log_level)

        self._orchestrator = SentinelSwarmOrchestrator()
        self._consumer = AsyncEventConsumer()
        self._neo4j = Neo4jClient()
        self._running = False

    async def start(self) -> None:
        """Start the full pipeline."""
        logger.info("pipeline_starting")
        self._running = True

        # Start Kafka consumer
        await self._consumer.start()
        logger.info("kafka_consumer_started")

        # Main processing loop
        while self._running:
            event = await self._consumer.get_event(timeout=2.0)
            if event is None:
                continue

            # Process in background to not block consumer
            asyncio.create_task(self._process_event(event))

    async def stop(self) -> None:
        """Gracefully stop the pipeline."""
        self._running = False
        await self._consumer.stop()
        self._neo4j.close()
        logger.info("pipeline_stopped")

    async def _process_event(self, event: EnrichedEvent) -> None:
        """Process a single event through the full pipeline."""
        try:
            # Ingest into graph
            self._neo4j.ingest_event(event)

            # Run through agent swarm
            result = await self._orchestrator.process_event(event)

            # Log final result
            self._log_result(result)

        except Exception as e:
            logger.error(
                "event_processing_failed",
                event_id=event.event.event_id,
                error=str(e),
                exc_info=True,
            )

    def _log_result(self, result: CaseState) -> None:
        """Log the final result of case processing."""
        logger.info(
            "case_result",
            case_id=result.case_id,
            status=result.status,
            verdict=result.verdict.value if result.verdict else None,
            score=result.final_confidence_score,
            latency_ms=result.total_latency_ms,
            errors=result.error_log,
        )


async def main() -> None:
    """Entry point for running the pipeline."""
    pipeline = SentinelSwarmPipeline()
    try:
        await pipeline.start()
    except KeyboardInterrupt:
        logger.info("shutdown_requested")
    finally:
        await pipeline.stop()


if __name__ == "__main__":
    asyncio.run(main())
