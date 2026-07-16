"""Tests for Pydantic data models."""

from __future__ import annotations

from datetime import datetime

import pytest

from sentinel_swarm.models.agents import (
    AgentReport,
    ExecutorReport,
    JuristReport,
    OSINTReport,
    PatternReport,
    SentinelReport,
    HistorianReport,
    Verdict,
    IdentityAssessment,
    PatternMatch,
    PatternMatchStatus,
    PatternType,
    PatternScale,
    ROSDestination,
    ScoreBreakdown,
    ActionResult,
    Precedent,
)
from sentinel_swarm.models.case import CaseState, CaseStatus
from sentinel_swarm.models.events import BankingEvent, EnrichedEvent, EventType
from sentinel_swarm.models.graph import GraphNode, GraphRelation, NodeType, RelationType, SubGraph


class TestBankingEvent:
    def test_valid_event(self, sample_event):
        assert sample_event.event_type == EventType.TRANSFER
        assert sample_event.country == "UY"
        assert sample_event.amount == 15_000.0

    def test_country_validation(self):
        with pytest.raises(Exception):
            BankingEvent(
                event_id="E1", event_type=EventType.LOGIN,
                timestamp=datetime.utcnow(), account_id="A1",
                user_id="U1", country="BR",
            )

    def test_enriched_event(self, enriched_event):
        assert enriched_event.event.event_id == "EVT-001"
        assert enriched_event.geo is not None
        assert enriched_event.geo.country == "Uruguay"
        assert enriched_event.device is not None
        assert enriched_event.history is not None
        assert enriched_event.history.events_last_1h == 3


class TestGraphModels:
    def test_graph_node(self):
        node = GraphNode(
            node_id="N1", node_type=NodeType.CUENTA,
            properties={"balance": 1000}, labels=["Cuenta", "HighRisk"],
        )
        assert node.node_type == NodeType.CUENTA
        assert "HighRisk" in node.labels

    def test_subgraph(self):
        sg = SubGraph(
            nodes=[
                GraphNode(node_id="N1", node_type=NodeType.CUENTA),
                GraphNode(node_id="N2", node_type=NodeType.PERSONA),
            ],
            relations=[
                GraphRelation(source_id="N2", target_id="N1", relation_type=RelationType.ES_TITULAR_DE),
            ],
            center_node_id="N1",
        )
        assert sg.node_count == 2
        assert sg.edge_count == 1


class TestAgentReports:
    def test_sentinel_report(self):
        report = SentinelReport(
            case_id="C1", risk_score=0.75, confidence=0.85,
            pattern_detected="RING_ATTACK",
            findings=["Cycle detected"],
        )
        assert report.agent_id == "sentinel"
        assert report.risk_score == 0.75

    def test_osint_report(self):
        report = OSINTReport(
            case_id="C1", risk_score=0.40, confidence=0.70,
            identity_assessment=IdentityAssessment.PARTIALLY_VERIFIED,
            legitimacy_score=0.60,
        )
        assert report.agent_id == "osint"
        assert report.identity_assessment == IdentityAssessment.PARTIALLY_VERIFIED

    def test_pattern_report(self):
        report = PatternReport(
            case_id="C1", risk_score=0.80, confidence=0.90,
            pattern_match=PatternMatch(
                pattern_id=PatternType.SMURFING,
                similarity_pct=85.0,
                match_status=PatternMatchStatus.CONFIRMED,
            ),
            scale_assessment=PatternScale.ORGANIZED_RING,
        )
        assert report.pattern_match is not None
        assert report.pattern_match.match_status == PatternMatchStatus.CONFIRMED

    def test_historian_report(self):
        report = HistorianReport(
            case_id="C1", risk_score=0.70, confidence=0.90,
            historical_fraud_rate=0.80,
            precedent_count=5,
            top_precedents=[
                Precedent(
                    case_id="H1", similarity_pct=90.0, result="FRAUD_CONFIRMED",
                    action_taken="Blocked", losses_usd=50_000.0,
                ),
            ],
        )
        assert report.historical_fraud_rate == 0.80
        assert len(report.top_precedents) == 1

    def test_jurist_report_verdict_block(self):
        report = JuristReport(
            case_id="C1", risk_score=0.90, confidence=0.95,
            verdict=Verdict.BLOCK,
            confidence_score=0.90,
            ros_required=True,
            ros_destination=ROSDestination.UIAF_UY,
            actions_ordered=["BLOCK_ACCOUNT", "GENERATE_ROS"],
        )
        assert report.verdict == Verdict.BLOCK
        assert report.ros_required is True

    def test_executor_report(self):
        report = ExecutorReport(
            case_id="C1", risk_score=0.90, confidence=1.0,
            execution_status="COMPLETED",
            actions_executed=[
                ActionResult(action="BLOCK_ACCOUNT", status="SUCCESS", rollback_id="RB-123"),
            ],
            graph_updated=True,
        )
        assert report.execution_status == "COMPLETED"
        assert len(report.actions_executed) == 1

    def test_risk_score_bounds(self):
        with pytest.raises(Exception):
            AgentReport(agent_id="test", case_id="C1", risk_score=1.5, confidence=0.5)

        with pytest.raises(Exception):
            AgentReport(agent_id="test", case_id="C1", risk_score=-0.1, confidence=0.5)


class TestCaseState:
    def test_initial_state(self, case_state):
        assert case_state.status == CaseStatus.OPEN
        assert case_state.verdict is None
        assert case_state.sentinel_report is None
        assert case_state.total_latency_ms == 0

    def test_state_with_reports(self, case_with_all_agents):
        state = case_with_all_agents
        assert state.sentinel_report is not None
        assert state.osint_report is not None
        assert state.pattern_report is not None
        assert state.historian_report is not None
        assert state.sentinel_report.risk_score == 0.72


class TestVerdicts:
    def test_verdict_enum(self):
        assert Verdict.BLOCK.value == "BLOCK"
        assert Verdict.MONITOR.value == "MONITOR"
        assert Verdict.ESCALATE.value == "ESCALATE"
        assert Verdict.DISCARD.value == "DISCARD"

    def test_ros_destination(self):
        assert ROSDestination.UIAF_UY.value == "UIAF_UY"
        assert ROSDestination.UIF_AR.value == "UIF_AR"
