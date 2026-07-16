"""Shared test fixtures for Sentinel Swarm."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel_swarm.models.agents import (
    IdentityAssessment,
    OSINTReport,
    PatternMatch,
    PatternMatchStatus,
    PatternReport,
    PatternScale,
    PatternType,
    SentinelReport,
    HistorianReport,
    Precedent,
    Verdict,
)
from sentinel_swarm.models.case import CaseState, CaseStatus
from sentinel_swarm.models.events import (
    BankingEvent,
    DeviceReputation,
    EnrichedEvent,
    EventType,
    GeoLocation,
    RecentHistory,
)
from sentinel_swarm.models.graph import SubGraph


@pytest.fixture
def sample_event() -> BankingEvent:
    return BankingEvent(
        event_id="EVT-001",
        event_type=EventType.TRANSFER,
        timestamp=datetime(2024, 6, 15, 14, 30, 0),
        account_id="ACC-UY-12345",
        user_id="USR-001",
        country="UY",
        amount=15_000.0,
        currency="USD",
        destination_account="ACC-AR-67890",
        destination_country="AR",
        device_id="DEV-AAAA",
        ip_address="190.64.100.50",
        document_type="cedula",
        document_number="1.234.567-8",
        metadata={"email": "test@example.com", "phone": "+598991234567", "name": "Juan Pérez"},
    )


@pytest.fixture
def sample_geo() -> GeoLocation:
    return GeoLocation(
        ip="190.64.100.50",
        country="Uruguay",
        city="Montevideo",
        latitude=-34.9011,
        longitude=-56.1645,
        is_vpn=False,
        is_tor=False,
        isp="Antel",
    )


@pytest.fixture
def sample_device() -> DeviceReputation:
    return DeviceReputation(
        device_id="DEV-AAAA",
        device_type="mobile",
        os="Android 14",
        known_fraud=False,
        accounts_linked=1,
    )


@pytest.fixture
def enriched_event(sample_event, sample_geo, sample_device) -> EnrichedEvent:
    return EnrichedEvent(
        event=sample_event,
        geo=sample_geo,
        device=sample_device,
        history=RecentHistory(
            events_last_1h=3,
            events_last_24h=8,
            total_amount_24h=25_000.0,
        ),
    )


@pytest.fixture
def case_state(enriched_event) -> CaseState:
    return CaseState(
        case_id="CASE-test-001",
        enriched_event=enriched_event,
        country="UY",
    )


@pytest.fixture
def case_with_sentinel(case_state) -> CaseState:
    case_state.sentinel_report = SentinelReport(
        case_id=case_state.case_id,
        risk_score=0.72,
        confidence=0.80,
        pattern_detected="RING_ATTACK",
        findings=["Transfer cycle detected: ACC-1 → ACC-2 → ACC-3 → ACC-1"],
        suspect_nodes=["ACC-1", "ACC-2", "ACC-3"],
    )
    return case_state


@pytest.fixture
def case_with_all_agents(case_with_sentinel) -> CaseState:
    state = case_with_sentinel
    state.osint_report = OSINTReport(
        case_id=state.case_id,
        risk_score=0.35,
        confidence=0.70,
        identity_assessment=IdentityAssessment.PARTIALLY_VERIFIED,
        legitimacy_score=0.65,
    )
    state.pattern_report = PatternReport(
        case_id=state.case_id,
        risk_score=0.75,
        confidence=0.85,
        pattern_match=PatternMatch(
            pattern_id=PatternType.SMURFING,
            similarity_pct=82.5,
            match_status=PatternMatchStatus.CONFIRMED,
        ),
        scale_assessment=PatternScale.SMALL_NETWORK,
    )
    state.historian_report = HistorianReport(
        case_id=state.case_id,
        risk_score=0.80,
        confidence=0.90,
        historical_fraud_rate=0.80,
        precedent_count=5,
        top_precedents=[
            Precedent(
                case_id="HIST-001", similarity_pct=88.0, result="FRAUD_CONFIRMED",
                action_taken="Account blocked", losses_usd=45_000.0,
            ),
        ],
    )
    return state


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM that returns valid JSON responses."""
    llm = AsyncMock()
    llm.bind_tools = MagicMock(return_value=llm)

    response = MagicMock()
    response.content = '{"risk_score": 0.7, "confidence": 0.8, "pattern_detected": "RING_ATTACK", "findings": ["test"], "suspect_nodes": [], "risk_multipliers": {}, "recommendation": "INVESTIGATE", "detailed_findings": []}'
    llm.ainvoke = AsyncMock(return_value=response)

    return llm
