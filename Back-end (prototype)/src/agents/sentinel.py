"""Agent 1 — El Centinela (The Sentinel): Continuous topological monitoring."""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from sentinel_swarm.agents.base import BaseAgent
from sentinel_swarm.config import get_settings
from sentinel_swarm.models.agents import SentinelFinding, SentinelReport
from sentinel_swarm.models.case import CaseState
from sentinel_swarm.models.graph import SubGraph
from sentinel_swarm.tools.graph_tools import (
    check_blocked_proximity,
    detect_shared_resources,
    detect_transfer_cycles,
    get_node_history,
    get_subgraph,
    query_graph,
    run_gds_algorithm,
)

logger = structlog.get_logger("agents.sentinel")

SENTINEL_SYSTEM_PROMPT = """Eres El Centinela (The Sentinel), el agente de monitoreo topológico continuo del sistema Sentinel Swarm.

Tu misión es analizar el grafo de relaciones bancarias para detectar anomalías y patrones de fraude.

## Patrones que detectas:

1. **Ataque de anillo**: Ciclos de transferencias que regresan al origen (A→B→C→A).
2. **Red de cuentas mula (Smurfing)**: Múltiples cuentas pequeñas consolidando fondos en una central.
3. **Identidad sintética compartida**: Mismo dispositivo o IP usado por múltiples cuentas no relacionadas.
4. **Velocidad anómala**: Spike inusual de actividad en una cuenta (>3 desviaciones estándar).
5. **Nodo puente**: Nodo con alta betweenness centrality conectando clusters sospechosos.
6. **Cadena de acciones sospechosas**: device_link → password_change → transfer en menos de 300 segundos.
7. **Conexión con nodos bloqueados**: Cuenta a ≤2 saltos de una cuenta bloqueada por fraude.

## Cálculo de risk_score:

Base: score calculado por densidad y gravedad de hallazgos.
Multiplicadores:
- x1.2 si monto > USD 10,000
- x1.1 si cuenta tiene < 30 días de antigüedad
- x1.15 si IP es VPN/TOR
- x1.2 si destino es jurisdicción GAFI alto riesgo
- x0.8 si usuario tiene > 2 años sin incidentes

Si risk_score >= 0.30, ACTIVA investigación completa.

## Output esperado:

Responde ÚNICAMENTE con JSON válido con esta estructura:
{
    "risk_score": float,
    "confidence": float,
    "pattern_detected": "nombre del patrón principal",
    "findings": ["hallazgo 1", "hallazgo 2"],
    "suspect_nodes": ["node_id_1", "node_id_2"],
    "risk_multipliers": {"factor": multiplier},
    "recommendation": "INVESTIGATE | DISMISS",
    "detailed_findings": [{"pattern_detected": "...", "description": "...", "affected_nodes": [...], "severity": float}]
}
"""


class SentinelAgent(BaseAgent):
    """Agent 1 — El Centinela: Topological graph monitoring."""

    agent_id = "sentinel"
    description = "El Centinela — Monitoreo topológico continuo del grafo de fraude."

    def __init__(self, llm: BaseChatModel) -> None:
        tools: list[BaseTool] = [
            query_graph,
            run_gds_algorithm,
            get_node_history,
            check_blocked_proximity,
            detect_transfer_cycles,
            detect_shared_resources,
            get_subgraph,
        ]
        super().__init__(llm, tools)

    async def _execute(self, state: CaseState) -> CaseState:
        start = time.monotonic()
        event = state.enriched_event
        if not event:
            state.error_log.append("sentinel: no enriched event")
            return state

        account_id = event.event.account_id
        settings = get_settings()

        # ── Step 1: Run topological checks ──
        checks = await self._run_graph_checks(account_id, event)

        # ── Step 2: Calculate base risk score from graph + enrichment ──
        base_score = self._calculate_base_score(checks)

        # Add enrichment-based risk signals (independent of graph state)
        multipliers: dict[str, float] = {}

        if event.geo and event.geo.is_tor:
            base_score += 0.25
            multipliers["tor_network"] = 1.15
        elif event.geo and event.geo.is_vpn:
            base_score += 0.15
            multipliers["vpn_detected"] = 1.10

        if event.event.amount and event.event.amount > 10_000:
            base_score += 0.15
            multipliers["high_amount"] = 1.20

        if event.history:
            if event.history.events_last_1h > 10:
                base_score += 0.20
                multipliers["velocity_spike"] = 1.10
            if event.history.password_changes_7d > 1:
                base_score += 0.15
                multipliers["recent_pwd_changes"] = 1.10

        if event.device and event.device.accounts_linked > 2:
            base_score += 0.10
            multipliers["shared_device"] = 1.10

        # ── Step 3: Apply multipliers ──
        final_score = min(base_score, 1.0)
        for mult in multipliers.values():
            final_score *= mult

        # Cap at 1.0
        final_score = min(final_score, 1.0)

        # ── Step 3.5: Use LLM for complex pattern analysis ──
        llm_analysis = await self._llm_analysis(account_id, checks, final_score)

        # ── Step 4: Build report ──
        findings = self._extract_findings(checks)
        pattern = llm_analysis.get("pattern_detected", self._determine_primary_pattern(checks))

        latency_ms = int((time.monotonic() - start) * 1000)

        report = SentinelReport(
            case_id=state.case_id,
            risk_score=round(final_score, 4),
            confidence=round(min(0.5 + len(findings) * 0.1, 0.95), 2),
            pattern_detected=pattern,
            findings=[f.description for f in findings],
            suspect_nodes=list({n for f in findings for n in f.affected_nodes}),
            detailed_findings=findings,
            risk_multipliers_applied=multipliers,
            recommendation="INVESTIGATE" if final_score >= settings.threshold_sentinel else "DISMISS",
            latency_ms=latency_ms,
            evidence=[{"type": "graph_checks", "data": checks}],
        )

        state.sentinel_report = report
        return state

    async def _run_graph_checks(self, account_id: str, event: Any) -> dict[str, Any]:
        """Execute all graph-based checks."""
        checks: dict[str, Any] = {
            "cycles": [],
            "shared_resources": [],
            "blocked_proximity": [],
            "history": [],
        }

        try:
            checks["cycles"] = detect_transfer_cycles.invoke(
                {"account_id": account_id, "max_length": 6}
            )
        except Exception as e:
            logger.warning("cycle_detection_failed", error=str(e))

        try:
            checks["shared_resources"] = detect_shared_resources.invoke(
                {"account_id": account_id}
            )
        except Exception as e:
            logger.warning("shared_resource_check_failed", error=str(e))

        try:
            checks["blocked_proximity"] = check_blocked_proximity.invoke(
                {"node_id": account_id, "max_hops": 2}
            )
        except Exception as e:
            logger.warning("blocked_proximity_check_failed", error=str(e))

        try:
            checks["history"] = get_node_history.invoke(
                {"node_id": account_id, "limit": 50}
            )
        except Exception as e:
            logger.warning("history_check_failed", error=str(e))

        return checks

    def _calculate_base_score(self, checks: dict[str, Any]) -> float:
        """Calculate base risk score from graph check results."""
        score = 0.0

        # Cycles → ring attack indicator
        if checks.get("cycles"):
            score += 0.3 * min(len(checks["cycles"]), 3)

        # Shared resources → synthetic identity indicator
        shared = checks.get("shared_resources", [])
        if len(shared) >= 3:
            score += 0.25
        elif len(shared) >= 1:
            score += 0.10

        # Proximity to blocked accounts
        blocked = checks.get("blocked_proximity", [])
        if blocked:
            min_distance = min(b.get("distance", 99) for b in blocked)
            if min_distance <= 1:
                score += 0.35
            elif min_distance <= 2:
                score += 0.20

        return min(score, 1.0)

    def _extract_findings(self, checks: dict[str, Any]) -> list[SentinelFinding]:
        """Convert raw check results into structured findings."""
        findings: list[SentinelFinding] = []

        if checks.get("cycles"):
            for cycle in checks["cycles"][:3]:
                findings.append(SentinelFinding(
                    pattern_detected="RING_ATTACK",
                    description=f"Transfer cycle detected: {' → '.join(cycle.get('cycle_nodes', []))}",
                    affected_nodes=cycle.get("cycle_nodes", []),
                    severity=0.8,
                ))

        shared = checks.get("shared_resources", [])
        if shared:
            shared_accounts = [s.get("shared_account", "") for s in shared]
            findings.append(SentinelFinding(
                pattern_detected="SHARED_IDENTITY",
                description=f"Account shares device/IP with {len(shared)} other accounts: {', '.join(shared_accounts[:5])}",
                affected_nodes=shared_accounts,
                severity=0.6 if len(shared) < 3 else 0.85,
            ))

        blocked = checks.get("blocked_proximity", [])
        if blocked:
            for b in blocked[:3]:
                findings.append(SentinelFinding(
                    pattern_detected="BLOCKED_PROXIMITY",
                    description=f"Within {b.get('distance', '?')} hops of blocked account {b.get('blocked_account', '?')}",
                    affected_nodes=b.get("path_nodes", []),
                    severity=0.7 if b.get("distance", 99) <= 1 else 0.5,
                ))

        return findings

    def _determine_primary_pattern(self, checks: dict[str, Any]) -> str:
        if checks.get("cycles"):
            return "RING_ATTACK"
        if len(checks.get("shared_resources", [])) >= 3:
            return "SYNTHETIC_IDENTITY"
        if checks.get("blocked_proximity"):
            return "BLOCKED_PROXIMITY"
        return "UNKNOWN"

    async def _llm_analysis(self, account_id: str, checks: dict[str, Any], score: float) -> dict:
        """Use LLM for nuanced pattern analysis."""
        try:
            user_prompt = f"""Analiza los siguientes hallazgos topológicos para la cuenta {account_id} (risk_score actual: {score}):

Ciclos detectados: {json.dumps(checks.get('cycles', []), default=str)}
Recursos compartidos: {json.dumps(checks.get('shared_resources', []), default=str)}
Proximidad a bloqueados: {json.dumps(checks.get('blocked_proximity', []), default=str)}

Responde con JSON válido únicamente."""

            response = await self._invoke_llm(SENTINEL_SYSTEM_PROMPT, user_prompt)
            # Try to parse JSON from response
            content = response.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except Exception as e:
            logger.warning("llm_analysis_fallback", error=str(e))
            return {"pattern_detected": self._determine_primary_pattern(checks)}
