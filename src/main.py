"""Sentinel Swarm — Main entry point.

Usage:
    python -m sentinel_swarm.main              # Run full pipeline (Kafka → Agents)
    python -m sentinel_swarm.main --test-event # Process a single test event
"""

from __future__ import annotations

import asyncio
import argparse
import sys
from datetime import datetime

from sentinel_swarm.config import get_settings
from sentinel_swarm.models.events import (
    BankingEvent,
    DeviceReputation,
    EnrichedEvent,
    EventType,
    GeoLocation,
    RecentHistory,
)
from sentinel_swarm.orchestrator.graph import SentinelSwarmOrchestrator
from sentinel_swarm.orchestrator.pipeline import main as run_pipeline
from sentinel_swarm.utils.logging import setup_logging


def create_test_event() -> EnrichedEvent:
    """Create a synthetic suspicious event for testing the pipeline."""
    event = BankingEvent(
        event_id="TEST-EVT-001",
        event_type=EventType.TRANSFER,
        timestamp=datetime.utcnow(),
        account_id="ACC-UY-TEST-001",
        user_id="USR-TEST-001",
        country="UY",
        amount=25_000.0,
        currency="USD",
        destination_account="ACC-AR-TEST-002",
        destination_country="AR",
        device_id="DEV-TEST-AAAA",
        ip_address="185.220.101.1",  # Known TOR exit node
        document_type="cedula",
        document_number="1.234.567-8",
        metadata={
            "email": "test.suspicious@tempmail.com",
            "phone": "+598991234567",
            "name": "Juan Test",
        },
    )

    return EnrichedEvent(
        event=event,
        geo=GeoLocation(
            ip="185.220.101.1",
            country="Germany",
            city="Frankfurt",
            is_vpn=True,
            is_tor=True,
        ),
        device=DeviceReputation(
            device_id="DEV-TEST-AAAA",
            known_fraud=False,
            accounts_linked=3,
        ),
        history=RecentHistory(
            events_last_1h=12,
            events_last_24h=45,
            total_amount_24h=150_000.0,
            unique_destinations_24h=8,
            password_changes_7d=2,
        ),
    )


async def run_test_event() -> None:
    """Process a single test event through the orchestrator."""
    settings = get_settings()
    setup_logging(settings.log_level)

    print("=" * 70)
    print("SENTINEL SWARM — Test Event Processing")
    print("=" * 70)

    orchestrator = SentinelSwarmOrchestrator()
    event = create_test_event()

    print(f"\nProcessing event: {event.event.event_id}")
    print(f"  Account:     {event.event.account_id}")
    print(f"  Type:        {event.event.event_type}")
    print(f"  Amount:      {event.event.amount} {event.event.currency}")
    print(f"  Destination: {event.event.destination_account}")
    print(f"  IP:          {event.event.ip_address} (VPN={event.geo.is_vpn}, TOR={event.geo.is_tor})")
    print()

    result = await orchestrator.process_event(event)

    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"  Case ID:    {result.case_id}")
    print(f"  Status:     {result.status}")
    print(f"  Verdict:    {result.verdict.value if result.verdict else 'N/A'}")
    print(f"  Score:      {result.final_confidence_score}")
    print(f"  Latency:    {result.total_latency_ms}ms")

    if result.sentinel_report:
        print(f"\n  [Sentinel]  Score={result.sentinel_report.risk_score:.4f}  Pattern={result.sentinel_report.pattern_detected}")
    if result.osint_report:
        print(f"  [OSINT]     Score={result.osint_report.risk_score:.4f}  Identity={result.osint_report.identity_assessment}")
    if result.pattern_report:
        pm = result.pattern_report.pattern_match
        print(f"  [Patterns]  Score={result.pattern_report.risk_score:.4f}  Match={pm.pattern_id if pm else 'N/A'}")
    if result.historian_report:
        print(f"  [Historian] Score={result.historian_report.risk_score:.4f}  FraudRate={result.historian_report.historical_fraud_rate:.0%}")
    if result.jurist_report:
        print(f"  [Jurist]    Score={result.jurist_report.confidence_score:.4f}  Verdict={result.jurist_report.verdict}")
        if result.jurist_report.ros_required:
            print(f"              ROS → {result.jurist_report.ros_destination}")
    if result.executor_report:
        print(f"  [Executor]  Status={result.executor_report.execution_status}  Actions={len(result.executor_report.actions_executed)}")

    if result.error_log:
        print(f"\n  Errors: {result.error_log}")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Sentinel Swarm — AROS")
    parser.add_argument("--test-event", action="store_true", help="Process a single test event")
    args = parser.parse_args()

    if args.test_event:
        asyncio.run(run_test_event())
    else:
        asyncio.run(run_pipeline())


if __name__ == "__main__":
    main()
