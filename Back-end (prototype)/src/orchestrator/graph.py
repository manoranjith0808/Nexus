"""LangGraph orchestrator — coordinates the 6-agent pipeline with conditional branching."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Literal

import structlog
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from sentinel_swarm.agents.executor import ExecutorAgent
from sentinel_swarm.agents.historian import HistorianAgent
from sentinel_swarm.agents.jurist import JuristAgent
from sentinel_swarm.agents.osint import OSINTAgent
from sentinel_swarm.agents.patterns import PatternAgent
from sentinel_swarm.agents.sentinel import SentinelAgent
from sentinel_swarm.config import get_settings
from sentinel_swarm.models.agents import Verdict
from sentinel_swarm.models.case import CaseState, CaseStatus
from sentinel_swarm.models.events import EnrichedEvent

logger = structlog.get_logger("orchestrator")


def _create_openai_llm(model: str = "gpt-4o") -> ChatOpenAI:
    """Create an OpenAI LLM client."""
    settings = get_settings()
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        model=model,
        temperature=0.1,
        max_tokens=4096,
    )


class SentinelSwarmOrchestrator:
    """LangGraph-based orchestrator for the 6-agent fraud detection pipeline.

    Pipeline flow:
        Event → Sentinel → [OSINT + Patterns + Historian] (parallel) → Jurist → Executor
                    ↓ (if score < threshold)
                   END (dismiss)
    """

    def __init__(self) -> None:
        self._settings = get_settings()

        # ── Initialize LLMs (all via OpenAI) ──
        gpt4o = _create_openai_llm("gpt-4o")
        gpt4o_mini = _create_openai_llm("gpt-4o-mini")

        # ── Initialize agents ──
        self._sentinel = SentinelAgent(llm=gpt4o_mini)
        self._osint = OSINTAgent(llm=gpt4o)
        self._patterns = PatternAgent(llm=gpt4o_mini)
        self._historian = HistorianAgent(llm=gpt4o_mini)
        self._jurist = JuristAgent(llm=gpt4o)
        self._executor = ExecutorAgent(llm=gpt4o_mini)

        # ── Build graph ──
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build the LangGraph state graph with conditional branching."""
        workflow = StateGraph(CaseState)

        # ── Add nodes ──
        workflow.add_node("sentinel", self._run_sentinel)
        workflow.add_node("parallel_investigation", self._run_parallel_agents)
        workflow.add_node("jurist", self._run_jurist)
        workflow.add_node("executor", self._run_executor)

        # ── Entry point ──
        workflow.set_entry_point("sentinel")

        # ── Conditional edge after Sentinel ──
        workflow.add_conditional_edges(
            "sentinel",
            self._should_investigate,
            {
                "investigate": "parallel_investigation",
                "dismiss": END,
            },
        )

        # ── Sequential edges ──
        workflow.add_edge("parallel_investigation", "jurist")

        # ── Conditional edge after Jurist ──
        workflow.add_conditional_edges(
            "jurist",
            self._should_execute,
            {
                "execute": "executor",
                "end": END,
            },
        )

        workflow.add_edge("executor", END)

        return workflow.compile()

    # ── Node implementations ──

    async def _run_sentinel(self, state: CaseState) -> CaseState:
        """Run Agent 1 — El Centinela."""
        try:
            state = await asyncio.wait_for(
                self._sentinel.run(state),
                timeout=self._settings.timeout_sentinel,
            )
        except asyncio.TimeoutError:
            logger.warning("sentinel_timeout", case_id=state.case_id)
            state.error_log.append("sentinel: timeout")
        state.status = CaseStatus.INVESTIGATING
        return state

    async def _run_parallel_agents(self, state: CaseState) -> CaseState:
        """Run Agents 2, 3, 4 in parallel."""
        tasks = []

        if self._settings.parallel_agents:
            tasks = [
                self._run_agent_with_timeout(self._osint, state, self._settings.timeout_osint, "osint"),
                self._run_agent_with_timeout(self._patterns, state, self._settings.timeout_patterns, "patterns"),
                self._run_agent_with_timeout(self._historian, state, self._settings.timeout_historian, "historian"),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Merge results — each agent writes to a different field
            for result in results:
                if isinstance(result, CaseState):
                    if result.osint_report:
                        state.osint_report = result.osint_report
                    if result.pattern_report:
                        state.pattern_report = result.pattern_report
                    if result.historian_report:
                        state.historian_report = result.historian_report
                elif isinstance(result, Exception):
                    state.error_log.append(f"parallel_agent: {str(result)}")
        else:
            # Sequential fallback
            state = await self._run_agent_with_timeout(self._osint, state, self._settings.timeout_osint, "osint")
            state = await self._run_agent_with_timeout(self._patterns, state, self._settings.timeout_patterns, "patterns")
            state = await self._run_agent_with_timeout(self._historian, state, self._settings.timeout_historian, "historian")

        return state

    async def _run_jurist(self, state: CaseState) -> CaseState:
        """Run Agent 5 — El Jurista."""
        try:
            state = await asyncio.wait_for(
                self._jurist.run(state),
                timeout=self._settings.timeout_jurist,
            )
        except asyncio.TimeoutError:
            logger.error("jurist_timeout", case_id=state.case_id)
            state.error_log.append("jurist: timeout — escalating to human")
            state.verdict = Verdict.ESCALATE
            state.status = CaseStatus.DECIDED
        state.status = CaseStatus.DECIDED
        return state

    async def _run_executor(self, state: CaseState) -> CaseState:
        """Run Agent 6 — El Ejecutor."""
        try:
            state = await asyncio.wait_for(
                self._executor.run(state),
                timeout=self._settings.timeout_executor,
            )
        except asyncio.TimeoutError:
            logger.error("executor_timeout", case_id=state.case_id)
            state.error_log.append("executor: timeout — alerting compliance")
        state.status = CaseStatus.EXECUTED
        return state

    async def _run_agent_with_timeout(
        self, agent: Any, state: CaseState, timeout: int, name: str
    ) -> CaseState:
        """Run an agent with timeout, returning state on timeout (reducing weight)."""
        try:
            return await asyncio.wait_for(agent.run(state), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"{name}_timeout", case_id=state.case_id, timeout=timeout)
            state.error_log.append(f"{name}: timeout (weight reduced)")
            return state
        except Exception as e:
            logger.error(f"{name}_error", case_id=state.case_id, error=str(e))
            state.error_log.append(f"{name}: {str(e)}")
            return state

    # ── Conditional routing ──

    def _should_investigate(self, state: CaseState) -> Literal["investigate", "dismiss"]:
        """After Sentinel: investigate if risk_score >= threshold, else dismiss."""
        if state.sentinel_report and state.sentinel_report.risk_score >= self._settings.threshold_sentinel:
            logger.info(
                "investigation_triggered",
                case_id=state.case_id,
                score=state.sentinel_report.risk_score,
            )
            return "investigate"
        logger.info("case_dismissed", case_id=state.case_id)
        state.status = CaseStatus.CLOSED
        return "dismiss"

    def _should_execute(self, state: CaseState) -> Literal["execute", "end"]:
        """After Jurist: execute if verdict requires action."""
        if state.verdict in (Verdict.BLOCK, Verdict.ESCALATE, Verdict.MONITOR):
            return "execute"
        state.status = CaseStatus.CLOSED
        return "end"

    # ── Public API ──

    async def process_event(self, enriched_event: EnrichedEvent) -> CaseState:
        """Process a single enriched banking event through the full pipeline."""
        case_id = f"CASE-{uuid.uuid4().hex[:12]}"
        start = time.monotonic()

        state = CaseState(
            case_id=case_id,
            enriched_event=enriched_event,
            country=enriched_event.event.country,
        )

        logger.info(
            "pipeline_started",
            case_id=case_id,
            event_type=enriched_event.event.event_type,
            account=enriched_event.event.account_id,
        )

        try:
            # LangGraph invocation
            final_state = await self._graph.ainvoke(state)

            # If LangGraph returns a dict, reconstruct CaseState
            if isinstance(final_state, dict):
                final_state = CaseState(**final_state)

            total_latency = int((time.monotonic() - start) * 1000)
            final_state.total_latency_ms = total_latency

            logger.info(
                "pipeline_completed",
                case_id=case_id,
                verdict=final_state.verdict.value if final_state.verdict else "DISMISSED",
                score=final_state.final_confidence_score,
                latency_ms=total_latency,
                errors=len(final_state.error_log),
            )

            if total_latency > self._settings.max_latency_total_ms:
                logger.warning(
                    "sla_breach",
                    case_id=case_id,
                    latency_ms=total_latency,
                    max_ms=self._settings.max_latency_total_ms,
                )

            return final_state

        except Exception as e:
            total_latency = int((time.monotonic() - start) * 1000)
            logger.error("pipeline_failed", case_id=case_id, error=str(e), exc_info=True)
            state.error_log.append(f"pipeline: {str(e)}")
            state.total_latency_ms = total_latency
            return state
