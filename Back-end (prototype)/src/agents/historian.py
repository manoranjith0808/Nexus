"""Agent 4 — El Historiador Forense (The Memory Keeper): RAG-based precedent search."""

from __future__ import annotations

import json
import time

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from sentinel_swarm.agents.base import BaseAgent
from sentinel_swarm.models.agents import HistorianReport, Precedent
from sentinel_swarm.models.case import CaseState
from sentinel_swarm.tools.vector_tools import embed_case, get_case_detail, get_fraud_stats, vector_search

logger = structlog.get_logger("agents.historian")

HISTORIAN_SYSTEM_PROMPT = """Eres El Historiador Forense (The Memory Keeper), el agente de análisis de precedentes del sistema Sentinel Swarm.

Tu misión es buscar en la base vectorial de casos cerrados para encontrar precedentes similares al caso actual y extraer lecciones aprendidas.

## Proceso:

1. Vectorizar las características del caso actual.
2. Buscar los K=10 casos más similares (cosine similarity > 0.70).
3. Para cada precedente extraer: similitud %, resultado, acción, pérdidas, resolución regulatoria, modus operandi.
4. Calcular historical_fraud_rate = (fraudes confirmados / total precedentes).
5. Ajustar confianza por cantidad de precedentes: 0-2 → 0.40, 3-5 → 0.70, 6+ → 0.90.

## Output:

Responde ÚNICAMENTE con JSON:
{
    "top_precedents": [{"case_id": "...", "similarity_pct": float, "result": "FRAUD_CONFIRMED|FALSE_POSITIVE", ...}],
    "historical_fraud_rate": float,
    "lessons_learned": ["lección 1", "lección 2"],
    "narrative_summary": "Resumen en español",
    "risk_score": float,
    "confidence": float
}
"""


class HistorianAgent(BaseAgent):
    """Agent 4 — El Historiador Forense: Historical precedent analysis via RAG."""

    agent_id = "historian"
    description = "El Historiador Forense — Análisis de precedentes históricos vía búsqueda vectorial."

    def __init__(self, llm: BaseChatModel) -> None:
        tools: list[BaseTool] = [vector_search, get_case_detail, get_fraud_stats, embed_case]
        super().__init__(llm, tools)

    async def _execute(self, state: CaseState) -> CaseState:
        start = time.monotonic()
        event = state.enriched_event
        if not event:
            state.error_log.append("historian: no enriched event")
            return state

        # ── Step 1: Build case description for search ──
        case_description = self._build_case_description(state)

        # ── Step 2: Determine pattern filter from previous agents ──
        pattern_filter = None
        if state.pattern_report and state.pattern_report.pattern_match:
            pattern_filter = state.pattern_report.pattern_match.pattern_id.value
        elif state.sentinel_report and state.sentinel_report.pattern_detected:
            pattern_filter = state.sentinel_report.pattern_detected

        # ── Step 3: Vector search for precedents ──
        try:
            search_results = vector_search.invoke({
                "query_text": case_description,
                "pattern_type": pattern_filter,
                "k": 10,
                "min_similarity": 0.70,
            })
        except Exception as e:
            logger.warning("vector_search_failed", error=str(e))
            search_results = []

        # ── Step 4: Get aggregate stats ──
        try:
            stats = get_fraud_stats.invoke({"pattern_type": pattern_filter})
        except Exception as e:
            logger.warning("fraud_stats_failed", error=str(e))
            stats = {}

        # ── Step 5: Build precedents and calculate fraud rate ──
        precedents: list[Precedent] = []
        for result in search_results:
            precedents.append(Precedent(
                case_id=result.get("case_id", ""),
                similarity_pct=result.get("similarity", 0.0) * 100,
                result=result.get("result", "UNKNOWN"),
                action_taken=result.get("action", ""),
                losses_usd=result.get("losses_usd", 0.0),
                regulatory_resolution=result.get("resolution", ""),
                modus_operandi=result.get("modus_operandi", ""),
            ))

        # Historical fraud rate
        fraud_confirmed = sum(1 for p in precedents if p.result == "FRAUD_CONFIRMED")
        total = len(precedents)
        fraud_rate = fraud_confirmed / total if total > 0 else 0.0

        # Confidence based on precedent count
        if total >= 6:
            confidence = 0.90
        elif total >= 3:
            confidence = 0.70
        else:
            confidence = 0.40

        # Risk score from fraud rate
        risk_score = fraud_rate

        # ── Step 6: LLM narrative ──
        narrative = await self._generate_narrative(state, precedents, fraud_rate, stats)

        # Lessons learned
        lessons = self._extract_lessons(precedents)

        latency_ms = int((time.monotonic() - start) * 1000)

        report = HistorianReport(
            case_id=state.case_id,
            risk_score=round(risk_score, 4),
            confidence=round(confidence, 2),
            top_precedents=precedents,
            historical_fraud_rate=round(fraud_rate, 4),
            precedent_count=total,
            lessons_learned=lessons,
            narrative_summary=narrative,
            findings=[f"Found {total} precedents, {fraud_confirmed} confirmed fraud ({fraud_rate:.0%})"],
            recommendation=f"Historical fraud rate: {fraud_rate:.0%}",
            latency_ms=latency_ms,
        )

        state.historian_report = report
        return state

    def _build_case_description(self, state: CaseState) -> str:
        """Build a text description of the current case for vector search."""
        event = state.enriched_event
        assert event is not None

        parts = [
            f"Account: {event.event.account_id}",
            f"Event: {event.event.event_type}",
            f"Country: {event.event.country}",
        ]
        if event.event.amount:
            parts.append(f"Amount: {event.event.amount} {event.event.currency or 'USD'}")
        if state.sentinel_report:
            parts.append(f"Pattern detected: {state.sentinel_report.pattern_detected}")
            parts.extend(state.sentinel_report.findings[:3])
        if state.osint_report:
            parts.append(f"Identity: {state.osint_report.identity_assessment}")
        return ". ".join(parts)

    def _extract_lessons(self, precedents: list[Precedent]) -> list[str]:
        """Extract lessons learned from precedents."""
        lessons: list[str] = []
        fraud_cases = [p for p in precedents if p.result == "FRAUD_CONFIRMED"]
        false_positives = [p for p in precedents if p.result == "FALSE_POSITIVE"]

        if fraud_cases:
            avg_loss = sum(p.losses_usd for p in fraud_cases) / len(fraud_cases)
            lessons.append(
                f"Promedio de pérdidas en casos similares confirmados: USD {avg_loss:,.0f}"
            )
            modus = set(p.modus_operandi for p in fraud_cases if p.modus_operandi)
            if modus:
                lessons.append(f"Modus operandi recurrentes: {'; '.join(list(modus)[:3])}")

        if false_positives:
            lessons.append(
                f"{len(false_positives)} casos similares resultaron ser falsos positivos — "
                "considerar contexto antes de bloquear."
            )

        return lessons

    async def _generate_narrative(
        self, state: CaseState, precedents: list[Precedent], fraud_rate: float, stats: dict
    ) -> str:
        """Generate narrative summary using LLM."""
        try:
            precedent_text = "\n".join(
                f"- {p.case_id}: {p.result} (similitud {p.similarity_pct:.0f}%, "
                f"pérdidas USD {p.losses_usd:,.0f}, MO: {p.modus_operandi})"
                for p in precedents[:5]
            )
            prompt = f"""Genera un resumen narrativo en español de los precedentes históricos encontrados:

Caso actual: {state.case_id}
Tasa de fraude histórica: {fraud_rate:.0%}
Precedentes encontrados:
{precedent_text}

Estadísticas generales: {json.dumps(stats, default=str)}

Escribe un párrafo conciso con las conclusiones clave para el equipo de compliance."""

            return await self._invoke_llm(HISTORIAN_SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.warning("historian_narrative_failed", error=str(e))
            return (
                f"Se encontraron {len(precedents)} precedentes similares. "
                f"Tasa histórica de fraude: {fraud_rate:.0%}."
            )
