"""Agent 3 — El Arquitecto de Patrones (The Pattern Matcher): Subgraph classification."""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from sentinel_swarm.agents.base import BaseAgent
from sentinel_swarm.models.agents import (
    CriticalNode,
    NodeRole,
    PatternMatch,
    PatternMatchStatus,
    PatternReport,
    PatternScale,
    PatternType,
)
from sentinel_swarm.models.case import CaseState
from sentinel_swarm.tools.graph_tools import get_subgraph, query_graph, run_gds_algorithm

logger = structlog.get_logger("agents.patterns")

# ── Pattern library: topology signatures ──
PATTERN_TEMPLATES: dict[str, dict[str, Any]] = {
    "SMURFING": {
        "description": "Estrella→Embudo: múltiples nodos periféricos transfieren a un nodo central (consolidador)",
        "topology": "star_to_funnel",
        "min_nodes": 4,
        "indicators": ["high_in_degree_central", "low_out_degree_peripherals", "similar_amounts"],
    },
    "ACCOUNT_TAKEOVER": {
        "description": "Cadena lineal: device_link→password_change→transfer en secuencia rápida",
        "topology": "linear_chain",
        "min_nodes": 1,
        "indicators": ["rapid_action_sequence", "new_device", "password_change"],
    },
    "IDENTIDAD_SINTETICA": {
        "description": "Clúster denso: múltiples cuentas comparten dispositivos/IPs",
        "topology": "dense_cluster",
        "min_nodes": 3,
        "indicators": ["shared_devices", "shared_ips", "high_density"],
    },
    "LAYERING": {
        "description": "Cascada con ciclos: 4-8 capas de intermediarios con retroalimentación",
        "topology": "cascade_with_cycles",
        "min_nodes": 5,
        "indicators": ["multiple_layers", "cycle_presence", "cross_border"],
    },
    "FRAUDE_SEGUROS": {
        "description": "Grafo bipartito: separación clara entre reclamantes y beneficiarios",
        "topology": "bipartite",
        "min_nodes": 4,
        "indicators": ["bipartite_structure", "claim_patterns"],
    },
    "CARRUSEL_TARJETAS": {
        "description": "Estrella invertida: una tarjeta usada en múltiples comercios sospechosos",
        "topology": "inverse_star",
        "min_nodes": 3,
        "indicators": ["single_source_multiple_targets", "rapid_transactions"],
    },
    "ROUND_TRIPPING": {
        "description": "Ciclo directo: A→B→A con montos similares (ida y vuelta)",
        "topology": "direct_cycle",
        "min_nodes": 2,
        "indicators": ["bidirectional_transfers", "similar_amounts", "same_parties"],
    },
}

PATTERNS_SYSTEM_PROMPT = """Eres El Arquitecto de Patrones (The Pattern Matcher), el agente de clasificación de ataques del sistema Sentinel Swarm.

Tu misión es comparar el sub-grafo del caso contra la biblioteca de patrones de fraude conocidos y clasificar el tipo de ataque.

## Biblioteca de patrones:

1. SMURFING (estrella→embudo): Múltiples depósitos pequeños consolidados.
2. ACCOUNT_TAKEOVER (cadena lineal): Toma de control secuencial rápida.
3. IDENTIDAD_SINTÉTICA (clúster denso): Cuentas compartiendo identidad digital.
4. LAYERING (cascada con ciclos): Capas de intermediarios (4-8 niveles).
5. FRAUDE_SEGUROS (grafo bipartito): Fraude de seguros coordinado.
6. CARRUSEL_TARJETAS (estrella invertida): Uso masivo de una tarjeta.
7. ROUND_TRIPPING (ciclo directo): Transferencias circulares A→B→A.

## Criterios de matching:

- Similitud > 80%: CONFIRMED
- 60-80%: PARTIAL
- < 60%: UNKNOWN

## Escala:

- INDIVIDUAL_ATTACKER: 1-2 nodos
- SMALL_NETWORK: 3-10 nodos
- ORGANIZED_RING: 10+ nodos

## Output:

Responde ÚNICAMENTE con JSON:
{
    "pattern_match": {"pattern_id": "...", "similarity_pct": float, "match_status": "...", "description": "..."},
    "scale_assessment": "...",
    "critical_nodes": [{"node_id": "...", "role": "SOURCE|MULE|CONSOLIDATOR|BRIDGE", "centrality_score": float}],
    "topology_summary": "...",
    "risk_score": float,
    "confidence": float
}
"""


class PatternAgent(BaseAgent):
    """Agent 3 — El Arquitecto de Patrones: Subgraph pattern classification."""

    agent_id = "patterns"
    description = "El Arquitecto de Patrones — Clasificación de ataques por topología de sub-grafos."

    def __init__(self, llm: BaseChatModel) -> None:
        tools: list[BaseTool] = [
            get_subgraph,
            query_graph,
            run_gds_algorithm,
        ]
        super().__init__(llm, tools)

    async def _execute(self, state: CaseState) -> CaseState:
        start = time.monotonic()
        event = state.enriched_event
        if not event:
            state.error_log.append("patterns: no enriched event")
            return state

        account_id = event.event.account_id

        # ── Step 1: Extract subgraph ──
        try:
            subgraph_data = get_subgraph.invoke({"center_node_id": account_id, "hops": 2})
        except Exception as e:
            logger.warning("subgraph_extraction_failed", error=str(e))
            subgraph_data = {"nodes": [], "relations": []}

        node_count = len(subgraph_data.get("nodes", []))
        edge_count = len(subgraph_data.get("relations", []))

        # ── Step 2: Compute centrality ──
        centrality_data: list[dict] = []
        try:
            centrality_data = run_gds_algorithm.invoke(
                {"algorithm": "betweenness", "graph_name": "fraud_graph"}
            )
        except Exception as e:
            logger.warning("centrality_computation_failed", error=str(e))

        # ── Step 3: Use sentinel findings if available ──
        sentinel_pattern = ""
        if state.sentinel_report:
            sentinel_pattern = state.sentinel_report.pattern_detected

        # ── Step 4: LLM-based pattern matching ──
        llm_result = await self._classify_with_llm(
            account_id, subgraph_data, centrality_data, sentinel_pattern
        )

        # ── Step 5: Build report ──
        pattern_match = None
        if llm_result.get("pattern_match"):
            pm = llm_result["pattern_match"]
            try:
                pattern_match = PatternMatch(
                    pattern_id=PatternType(pm.get("pattern_id", "SMURFING")),
                    similarity_pct=pm.get("similarity_pct", 0.0),
                    match_status=PatternMatchStatus(pm.get("match_status", "UNKNOWN")),
                    description=pm.get("description", ""),
                )
            except (ValueError, KeyError):
                pass

        # Scale assessment
        scale = PatternScale.INDIVIDUAL_ATTACKER
        if node_count > 10:
            scale = PatternScale.ORGANIZED_RING
        elif node_count > 2:
            scale = PatternScale.SMALL_NETWORK

        # Critical nodes
        critical_nodes: list[CriticalNode] = []
        for cn in llm_result.get("critical_nodes", []):
            try:
                critical_nodes.append(CriticalNode(
                    node_id=cn["node_id"],
                    role=NodeRole(cn.get("role", "BRIDGE")),
                    centrality_score=cn.get("centrality_score", 0.0),
                ))
            except (ValueError, KeyError):
                pass

        risk_score = llm_result.get("risk_score", 0.3)
        if pattern_match and pattern_match.match_status == PatternMatchStatus.CONFIRMED:
            risk_score = max(risk_score, 0.7)

        latency_ms = int((time.monotonic() - start) * 1000)

        report = PatternReport(
            case_id=state.case_id,
            risk_score=round(min(risk_score, 1.0), 4),
            confidence=round(llm_result.get("confidence", 0.5), 2),
            pattern_match=pattern_match,
            scale_assessment=scale,
            critical_nodes=critical_nodes,
            topology_summary=llm_result.get("topology_summary", f"Subgraph: {node_count} nodes, {edge_count} edges"),
            findings=[f"Pattern: {pattern_match.pattern_id if pattern_match else 'UNKNOWN'}", f"Scale: {scale}"],
            recommendation=f"Pattern classification: {pattern_match.match_status if pattern_match else 'UNKNOWN'}",
            latency_ms=latency_ms,
        )

        state.pattern_report = report
        return state

    async def _classify_with_llm(
        self, account_id: str, subgraph: dict, centrality: list[dict], sentinel_hint: str
    ) -> dict:
        """Use LLM to classify the attack pattern."""
        try:
            prompt = f"""Analiza el siguiente sub-grafo y clasifica el patrón de ataque.

Cuenta central: {account_id}
Sub-grafo: {json.dumps(subgraph, default=str)[:3000]}
Centralidad (betweenness): {json.dumps(centrality[:10], default=str)}
Patrón sugerido por el Centinela: {sentinel_hint or 'ninguno'}

Biblioteca de patrones disponibles:
{json.dumps({k: v['description'] for k, v in PATTERN_TEMPLATES.items()}, ensure_ascii=False)}

Responde con JSON válido únicamente."""

            response = await self._invoke_llm(PATTERNS_SYSTEM_PROMPT, prompt)
            content = response.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except Exception as e:
            logger.warning("pattern_classification_fallback", error=str(e))
            return {
                "pattern_match": None,
                "scale_assessment": "UNKNOWN",
                "critical_nodes": [],
                "topology_summary": "LLM classification unavailable",
                "risk_score": 0.3,
                "confidence": 0.3,
            }
