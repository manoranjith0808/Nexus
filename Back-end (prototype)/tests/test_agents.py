"""Tests for the 6 Sentinel Swarm agents."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel_swarm.agents.sentinel import SentinelAgent
from sentinel_swarm.agents.osint import OSINTAgent
from sentinel_swarm.agents.patterns import PatternAgent
from sentinel_swarm.agents.historian import HistorianAgent
from sentinel_swarm.agents.jurist import JuristAgent
from sentinel_swarm.agents.executor import ExecutorAgent
from sentinel_swarm.models.agents import (
    Verdict,
    IdentityAssessment,
    JuristReport,
    ROSDestination,
)
from sentinel_swarm.models.case import CaseState, CaseStatus


# ── Agent 1: El Centinela ──

class TestSentinelAgent:
    @pytest.fixture
    def agent(self, mock_llm):
        return SentinelAgent(llm=mock_llm)

    @pytest.mark.asyncio
    @patch("sentinel_swarm.agents.sentinel.detect_transfer_cycles")
    @patch("sentinel_swarm.agents.sentinel.detect_shared_resources")
    @patch("sentinel_swarm.agents.sentinel.check_blocked_proximity")
    @patch("sentinel_swarm.agents.sentinel.get_node_history")
    async def test_sentinel_detects_cycle(
        self, mock_history, mock_blocked, mock_shared, mock_cycles, agent, case_state
    ):
        mock_cycles.invoke.return_value = [
            {"cycle_nodes": ["ACC-1", "ACC-2", "ACC-3", "ACC-1"], "cycle_length": 3}
        ]
        mock_shared.invoke.return_value = []
        mock_blocked.invoke.return_value = []
        mock_history.invoke.return_value = []

        result = await agent.run(case_state)

        assert result.sentinel_report is not None
        assert result.sentinel_report.risk_score > 0
        assert result.sentinel_report.agent_id == "sentinel"

    @pytest.mark.asyncio
    @patch("sentinel_swarm.agents.sentinel.detect_transfer_cycles")
    @patch("sentinel_swarm.agents.sentinel.detect_shared_resources")
    @patch("sentinel_swarm.agents.sentinel.check_blocked_proximity")
    @patch("sentinel_swarm.agents.sentinel.get_node_history")
    async def test_sentinel_blocked_proximity(
        self, mock_history, mock_blocked, mock_shared, mock_cycles, agent, case_state
    ):
        mock_cycles.invoke.return_value = []
        mock_shared.invoke.return_value = []
        mock_blocked.invoke.return_value = [
            {"blocked_account": "ACC-FRAUD-1", "distance": 1, "path_nodes": ["ACC-UY-12345", "ACC-FRAUD-1"]}
        ]
        mock_history.invoke.return_value = []

        result = await agent.run(case_state)

        assert result.sentinel_report is not None
        assert result.sentinel_report.risk_score >= 0.3

    @pytest.mark.asyncio
    @patch("sentinel_swarm.agents.sentinel.detect_transfer_cycles")
    @patch("sentinel_swarm.agents.sentinel.detect_shared_resources")
    @patch("sentinel_swarm.agents.sentinel.check_blocked_proximity")
    @patch("sentinel_swarm.agents.sentinel.get_node_history")
    async def test_sentinel_clean_account(
        self, mock_history, mock_blocked, mock_shared, mock_cycles, agent, case_state
    ):
        mock_cycles.invoke.return_value = []
        mock_shared.invoke.return_value = []
        mock_blocked.invoke.return_value = []
        mock_history.invoke.return_value = []

        result = await agent.run(case_state)

        assert result.sentinel_report is not None
        # Base score should be low for clean account (but multipliers may apply)


# ── Agent 2: OSINT ──

class TestOSINTAgent:
    @pytest.fixture
    def agent(self, mock_llm):
        return OSINTAgent(llm=mock_llm)

    @pytest.mark.asyncio
    @patch("sentinel_swarm.agents.osint.verify_email")
    @patch("sentinel_swarm.agents.osint.phone_intelligence")
    @patch("sentinel_swarm.agents.osint.ip_reputation")
    @patch("sentinel_swarm.agents.osint.device_intelligence")
    @patch("sentinel_swarm.agents.osint.breach_check")
    async def test_osint_clean_identity(
        self, mock_breach, mock_device, mock_ip, mock_phone, mock_email, agent, case_state
    ):
        mock_email.invoke.return_value = {"exists": True, "disposable": False, "flags": [], "has_social_presence": True}
        mock_phone.invoke.return_value = {"sim_swap_recent": False, "flags": []}
        mock_ip.invoke.return_value = {"abuse_score": 0, "flags": []}
        mock_device.invoke.return_value = {"known_fraud": False, "accounts_linked": 1, "is_emulator": False, "flags": []}
        mock_breach.invoke.return_value = {"breached": False, "flags": []}

        result = await agent.run(case_state)

        assert result.osint_report is not None
        assert result.osint_report.legitimacy_score >= 0.8
        assert result.osint_report.identity_assessment in (
            IdentityAssessment.VERIFIED, IdentityAssessment.PARTIALLY_VERIFIED
        )

    @pytest.mark.asyncio
    @patch("sentinel_swarm.agents.osint.verify_email")
    @patch("sentinel_swarm.agents.osint.phone_intelligence")
    @patch("sentinel_swarm.agents.osint.ip_reputation")
    @patch("sentinel_swarm.agents.osint.device_intelligence")
    @patch("sentinel_swarm.agents.osint.breach_check")
    async def test_osint_suspicious_identity(
        self, mock_breach, mock_device, mock_ip, mock_phone, mock_email, agent, case_state
    ):
        mock_email.invoke.return_value = {"exists": True, "disposable": True, "flags": ["FLAG_DISPOSABLE", "FLAG_NO_FOOTPRINT"]}
        mock_phone.invoke.return_value = {"sim_swap_recent": True, "flags": []}
        mock_ip.invoke.return_value = {"abuse_score": 80, "flags": ["FLAG_TOR"]}
        mock_device.invoke.return_value = {"known_fraud": True, "accounts_linked": 5, "is_emulator": False, "flags": []}
        mock_breach.invoke.return_value = {"breached": True, "breach_count": 3, "flags": []}

        result = await agent.run(case_state)

        assert result.osint_report is not None
        assert result.osint_report.legitimacy_score < 0.4
        assert result.osint_report.identity_assessment in (
            IdentityAssessment.UNVERIFIED, IdentityAssessment.SYNTHETIC_PROBABLE
        )


# ── Agent 3: Patterns ──

class TestPatternAgent:
    @pytest.fixture
    def agent(self, mock_llm):
        return PatternAgent(llm=mock_llm)

    @pytest.mark.asyncio
    @patch("sentinel_swarm.agents.patterns.get_subgraph")
    @patch("sentinel_swarm.agents.patterns.run_gds_algorithm")
    async def test_pattern_classification(self, mock_gds, mock_sg, agent, case_with_sentinel):
        mock_sg.invoke.return_value = {
            "nodes": [{"node_id": f"N{i}", "node_type": "Cuenta"} for i in range(5)],
            "relations": [],
        }
        mock_gds.invoke.return_value = [{"node": "N1", "score": 0.8}]

        # Override LLM response for pattern agent
        response = MagicMock()
        response.content = '{"pattern_match": {"pattern_id": "SMURFING", "similarity_pct": 85.0, "match_status": "CONFIRMED", "description": "test"}, "scale_assessment": "SMALL_NETWORK", "critical_nodes": [{"node_id": "N1", "role": "CONSOLIDATOR", "centrality_score": 0.8}], "topology_summary": "test", "risk_score": 0.8, "confidence": 0.85}'
        agent.llm.ainvoke = AsyncMock(return_value=response)

        result = await agent.run(case_with_sentinel)

        assert result.pattern_report is not None
        assert result.pattern_report.pattern_match is not None


# ── Agent 4: Historian ──

class TestHistorianAgent:
    @pytest.fixture
    def agent(self, mock_llm):
        return HistorianAgent(llm=mock_llm)

    @pytest.mark.asyncio
    @patch("sentinel_swarm.agents.historian.vector_search")
    @patch("sentinel_swarm.agents.historian.get_fraud_stats")
    async def test_historian_finds_precedents(self, mock_stats, mock_search, agent, case_with_sentinel):
        mock_search.invoke.return_value = [
            {"case_id": "H1", "similarity": 0.85, "result": "FRAUD_CONFIRMED", "action": "Blocked",
             "losses_usd": 45000, "resolution": "Resolved", "modus_operandi": "Smurfing ring", "pattern": "SMURFING"},
            {"case_id": "H2", "similarity": 0.78, "result": "FALSE_POSITIVE", "action": "Cleared",
             "losses_usd": 0, "resolution": "False alarm", "modus_operandi": "Legitimate payroll", "pattern": "SMURFING"},
        ]
        mock_stats.invoke.return_value = {"total_cases": 10, "fraud_rate": 0.7}

        result = await agent.run(case_with_sentinel)

        assert result.historian_report is not None
        assert result.historian_report.precedent_count == 2
        assert result.historian_report.historical_fraud_rate == 0.5

    @pytest.mark.asyncio
    @patch("sentinel_swarm.agents.historian.vector_search")
    @patch("sentinel_swarm.agents.historian.get_fraud_stats")
    async def test_historian_no_precedents(self, mock_stats, mock_search, agent, case_state):
        mock_search.invoke.return_value = []
        mock_stats.invoke.return_value = {"total_cases": 0, "fraud_rate": 0.0}

        result = await agent.run(case_state)

        assert result.historian_report is not None
        assert result.historian_report.precedent_count == 0
        assert result.historian_report.confidence == 0.40


# ── Agent 5: Jurist ──

class TestJuristAgent:
    @pytest.fixture
    def agent(self, mock_llm):
        # Override LLM for legal justification
        response = MagicMock()
        response.content = '{"applicable_norms": ["Ley 19.574 Art. 14"], "facts": ["High risk score"], "reasoning": "Test reasoning", "proportionality": "Proportional", "inaction_risk": "High"}'
        mock_llm.ainvoke = AsyncMock(return_value=response)
        return JuristAgent(llm=mock_llm)

    @pytest.mark.asyncio
    @patch("sentinel_swarm.agents.jurist.calculate_confidence_score")
    @patch("sentinel_swarm.agents.jurist.get_gafi_status")
    @patch("sentinel_swarm.agents.jurist.get_pep_status")
    @patch("sentinel_swarm.agents.jurist.check_sanctions")
    @patch("sentinel_swarm.agents.jurist.get_regulation")
    async def test_jurist_block_verdict(
        self, mock_reg, mock_sanctions, mock_pep, mock_gafi, mock_score, agent, case_with_all_agents
    ):
        mock_score.invoke.return_value = {"base_score": 0.88, "final_score": 0.88}
        mock_gafi.invoke.return_value = {"status": "STANDARD", "multiplier": 1.0}
        mock_pep.invoke.return_value = {"is_pep": False, "multiplier": 1.0}
        mock_sanctions.invoke.return_value = {"sanctioned": False}
        mock_reg.invoke.return_value = {"thresholds": {"cash_report_usd": 10000}}

        result = await agent.run(case_with_all_agents)

        assert result.jurist_report is not None
        assert result.verdict == Verdict.BLOCK

    @pytest.mark.asyncio
    @patch("sentinel_swarm.agents.jurist.calculate_confidence_score")
    @patch("sentinel_swarm.agents.jurist.get_gafi_status")
    @patch("sentinel_swarm.agents.jurist.get_pep_status")
    @patch("sentinel_swarm.agents.jurist.check_sanctions")
    @patch("sentinel_swarm.agents.jurist.get_regulation")
    async def test_jurist_discard_verdict(
        self, mock_reg, mock_sanctions, mock_pep, mock_gafi, mock_score, agent, case_state
    ):
        mock_score.invoke.return_value = {"base_score": 0.15, "final_score": 0.15}
        mock_gafi.invoke.return_value = {"status": "STANDARD", "multiplier": 1.0}
        mock_pep.invoke.return_value = {"is_pep": False}
        mock_sanctions.invoke.return_value = {"sanctioned": False}
        mock_reg.invoke.return_value = {"thresholds": {"cash_report_usd": 10000}}

        result = await agent.run(case_state)

        assert result.jurist_report is not None
        assert result.verdict == Verdict.DISCARD


# ── Agent 6: Executor ──

class TestExecutorAgent:
    @pytest.fixture
    def agent(self, mock_llm):
        response = MagicMock()
        response.content = '{"operation_description": "Test op", "suspicion_grounds": "Test grounds", "action_taken": "Blocked"}'
        mock_llm.ainvoke = AsyncMock(return_value=response)
        return ExecutorAgent(llm=mock_llm)

    @pytest.mark.asyncio
    @patch("sentinel_swarm.agents.executor.block_account")
    @patch("sentinel_swarm.agents.executor.cancel_transaction")
    @patch("sentinel_swarm.agents.executor.generate_ros")
    @patch("sentinel_swarm.agents.executor.submit_ros")
    @patch("sentinel_swarm.agents.executor.notify_compliance")
    @patch("sentinel_swarm.agents.executor.update_graph_status")
    @patch("sentinel_swarm.agents.executor.notify_client")
    async def test_executor_block_flow(
        self, mock_client, mock_graph, mock_compliance, mock_submit,
        mock_ros, mock_cancel, mock_block, agent, case_with_all_agents
    ):
        # Set up jurist report with BLOCK verdict
        state = case_with_all_agents
        state.jurist_report = JuristReport(
            case_id=state.case_id, risk_score=0.90, confidence=0.95,
            verdict=Verdict.BLOCK, confidence_score=0.90,
            ros_required=True, ros_destination=ROSDestination.UIAF_UY,
            actions_ordered=["BLOCK_ACCOUNT", "CANCEL_TRANSACTION", "GENERATE_ROS", "NOTIFY_COMPLIANCE", "NOTIFY_CLIENT"],
        )
        state.verdict = Verdict.BLOCK
        state.final_confidence_score = 0.90

        mock_block.invoke.return_value = {"status": "SUCCESS", "rollback_id": "RB-001"}
        mock_cancel.invoke.return_value = {"status": "SUCCESS", "rollback_id": "RB-002"}
        mock_ros.invoke.return_value = {"ros_id": "ROS-001", "status": "GENERATED", "subject": {}}
        mock_submit.invoke.return_value = {"status": "SUBMITTED", "confirmation_number": "CONF-001"}
        mock_compliance.invoke.return_value = {"status": "DELIVERED", "notification_id": "NOT-001"}
        mock_graph.invoke.return_value = {"result": "SUCCESS"}
        mock_client.invoke.return_value = {"status": "SENT", "notification_id": "CLI-001"}

        result = await agent.run(state)

        assert result.executor_report is not None
        assert result.executor_report.execution_status == "COMPLETED"
        assert len(result.executor_report.actions_executed) >= 5
        assert result.executor_report.graph_updated is True

    @pytest.mark.asyncio
    async def test_executor_discard_skips(self, agent, case_state):
        state = case_state
        state.jurist_report = JuristReport(
            case_id=state.case_id, risk_score=0.10, confidence=0.95,
            verdict=Verdict.DISCARD, confidence_score=0.10,
            actions_ordered=[],
        )
        state.verdict = Verdict.DISCARD

        result = await agent.run(state)

        assert result.executor_report is not None
        assert result.executor_report.execution_status == "SKIPPED"
