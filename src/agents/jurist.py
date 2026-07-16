"""Agent 5 — El Jurista de Compliance (The Judge): Legal evaluation and verdict."""

from __future__ import annotations

import json
import time

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from sentinel_swarm.agents.base import BaseAgent
from sentinel_swarm.config import get_settings
from sentinel_swarm.models.agents import (
    JuristReport,
    LegalJustification,
    ROSDestination,
    RegulatoryMultiplier,
    ScoreBreakdown,
    Verdict,
)
from sentinel_swarm.models.case import CaseState
from sentinel_swarm.tools.compliance_tools import (
    calculate_confidence_score,
    check_sanctions,
    get_gafi_status,
    get_pep_status,
    get_regulation,
)

logger = structlog.get_logger("agents.jurist")

JURIST_SYSTEM_PROMPT = """Eres El Jurista de Compliance (The Judge), el agente de evaluación legal y emisión de veredictos del sistema Sentinel Swarm.

Operas bajo las siguientes normativas:
- **Uruguay**: Ley 19.574 (PLA/FT), BCU, SENACLAFT, UIAF
- **Argentina**: Ley 25.246 mod. 26.683, BCRA Com. A 6399, UIF
- **Internacional**: GAFI/GAFILAT 40 Recomendaciones, OFAC, ONU, UE

## Score de Confianza:

C = Σ(Wi × Si) / ΣWi

Pesos por defecto:
- Centinela: 0.25
- OSINT: 0.20
- Patrones: 0.20
- Historiador: 0.15
- Jurista: 0.20

## Multiplicadores regulatorios:

- x1.15 si jurisdicción de destino es GAFI gris/negra
- x1.10 si el sujeto es PEP
- x1.10 si monto > umbral de reporte obligatorio
- x1.20 si match en listas de sanciones
- x0.90 si cliente > 5 años sin incidentes

## Veredictos:

- C < 0.40: DESCARTAR
- 0.40-0.65: MONITOREAR 72h
- 0.65-0.85: ESCALAR a humano
- C >= 0.85: BLOQUEAR

## Output:

Responde ÚNICAMENTE con JSON:
{
    "verdict": "DISCARD|MONITOR|ESCALATE|BLOCK",
    "confidence_score": float,
    "score_breakdown": [...],
    "regulatory_multipliers": [...],
    "legal_justification": {
        "applicable_norms": [...],
        "facts": [...],
        "reasoning": "...",
        "proportionality": "...",
        "inaction_risk": "..."
    },
    "actions_ordered": [...],
    "ros_required": bool,
    "ros_destination": "UIAF_UY|UIF_AR|BOTH|null"
}
"""


class JuristAgent(BaseAgent):
    """Agent 5 — El Jurista de Compliance: Legal evaluation and verdict."""

    agent_id = "jurist"
    description = "El Jurista de Compliance — Evaluación legal y emisión de veredictos."

    def __init__(self, llm: BaseChatModel) -> None:
        tools: list[BaseTool] = [
            get_regulation,
            check_sanctions,
            get_gafi_status,
            calculate_confidence_score,
            get_pep_status,
        ]
        super().__init__(llm, tools)

    async def _execute(self, state: CaseState) -> CaseState:
        start = time.monotonic()
        event = state.enriched_event
        if not event:
            state.error_log.append("jurist: no enriched event")
            return state

        settings = get_settings()
        country = event.event.country

        # ── Step 1: Collect agent scores ──
        scores = self._collect_agent_scores(state)

        # ── Step 2: Calculate base weighted score ──
        weights = settings.agent_weights
        score_result = calculate_confidence_score.invoke({
            "sentinel_score": scores["sentinel"],
            "osint_score": scores["osint"],
            "patterns_score": scores["patterns"],
            "historian_score": scores["historian"],
            "jurist_score": scores.get("jurist", 0.5),
            "weights": weights,
        })
        base_score = score_result.get("base_score", 0.0)

        # ── Step 3: Regulatory checks & multipliers ──
        multipliers: list[RegulatoryMultiplier] = []
        final_score = base_score

        # GAFI status of destination
        dest_country = event.event.destination_country
        if dest_country:
            gafi = get_gafi_status.invoke({"country_code": dest_country})
            if gafi.get("status") in ("HIGH_RISK", "GREY_LIST"):
                mult = gafi.get("multiplier", 1.15)
                multipliers.append(RegulatoryMultiplier(
                    factor="gafi_jurisdiction", multiplier=mult,
                    reason=f"Destination {dest_country} is GAFI {gafi['status']}",
                ))
                final_score *= mult

        # PEP check
        user_name = event.event.metadata.get("name", "")
        if user_name:
            pep = get_pep_status.invoke({"name": user_name, "country": country})
            if pep.get("is_pep"):
                multipliers.append(RegulatoryMultiplier(
                    factor="pep", multiplier=1.10,
                    reason=f"Subject is PEP: {pep.get('category', 'unknown')}",
                ))
                final_score *= 1.10

        # Sanctions check
        sanctions = check_sanctions.invoke({
            "name": user_name or event.event.user_id,
            "document_number": event.event.document_number,
        })
        if sanctions.get("sanctioned"):
            multipliers.append(RegulatoryMultiplier(
                factor="sanctions_match", multiplier=1.20,
                reason=f"Match in: {', '.join(sanctions.get('lists_matched', []))}",
            ))
            final_score *= 1.20

        # Amount threshold
        reg = get_regulation.invoke({"country": country, "topic": "thresholds"})
        thresholds = reg.get("thresholds", {})
        amount = event.event.amount or 0
        if country == "UY" and amount > thresholds.get("cash_report_usd", 10_000):
            multipliers.append(RegulatoryMultiplier(
                factor="amount_threshold", multiplier=1.10,
                reason=f"Amount USD {amount:,.0f} exceeds UY reporting threshold",
            ))
            final_score *= 1.10
        elif country == "AR" and amount > thresholds.get("cash_report_ars", 300_000):
            multipliers.append(RegulatoryMultiplier(
                factor="amount_threshold", multiplier=1.10,
                reason=f"Amount ARS {amount:,.0f} exceeds AR reporting threshold",
            ))
            final_score *= 1.10

        final_score = min(final_score, 1.0)

        # ── Step 4: Determine verdict ──
        if final_score >= settings.threshold_block:
            verdict = Verdict.BLOCK
        elif final_score >= settings.threshold_escalate:
            verdict = Verdict.ESCALATE
        elif final_score >= settings.threshold_monitor:
            verdict = Verdict.MONITOR
        else:
            verdict = Verdict.DISCARD

        # ── Step 5: Legal justification via LLM ──
        legal_justification = await self._generate_legal_justification(
            state, verdict, final_score, multipliers, country
        )

        # ── Step 6: Determine actions and ROS requirement ──
        actions = self._determine_actions(verdict)
        ros_required = verdict in (Verdict.BLOCK, Verdict.ESCALATE)
        ros_destination = self._determine_ros_destination(country) if ros_required else None

        # ── Step 7: Build score breakdown ──
        breakdown = [
            ScoreBreakdown(
                agent=name,
                raw_score=scores[name],
                weight=weights.get(name, 0.0),
                weighted_score=round(scores[name] * weights.get(name, 0.0), 4),
            )
            for name in ["sentinel", "osint", "patterns", "historian"]
        ]

        latency_ms = int((time.monotonic() - start) * 1000)

        report = JuristReport(
            case_id=state.case_id,
            risk_score=round(final_score, 4),
            confidence=round(min(0.6 + len(multipliers) * 0.05, 0.95), 2),
            verdict=verdict,
            confidence_score=round(final_score, 4),
            score_breakdown=breakdown,
            regulatory_multipliers=multipliers,
            legal_justification=legal_justification,
            actions_ordered=actions,
            ros_required=ros_required,
            ros_destination=ros_destination,
            findings=[f"Verdict: {verdict.value}", f"Score: {final_score:.4f}"],
            recommendation=f"{verdict.value} — Confidence: {final_score:.2%}",
            latency_ms=latency_ms,
        )

        state.jurist_report = report
        state.verdict = verdict
        state.final_confidence_score = round(final_score, 4)
        return state

    def _collect_agent_scores(self, state: CaseState) -> dict[str, float]:
        """Collect risk scores from all previous agents, defaulting to 0.5 if absent."""
        return {
            "sentinel": state.sentinel_report.risk_score if state.sentinel_report else 0.5,
            "osint": state.osint_report.risk_score if state.osint_report else 0.5,
            "patterns": state.pattern_report.risk_score if state.pattern_report else 0.5,
            "historian": state.historian_report.risk_score if state.historian_report else 0.5,
        }

    def _determine_actions(self, verdict: Verdict) -> list[str]:
        if verdict == Verdict.BLOCK:
            return ["BLOCK_ACCOUNT", "CANCEL_TRANSACTION", "GENERATE_ROS", "NOTIFY_COMPLIANCE", "NOTIFY_CLIENT"]
        if verdict == Verdict.ESCALATE:
            return ["GENERATE_ROS", "NOTIFY_COMPLIANCE"]
        if verdict == Verdict.MONITOR:
            return ["MONITOR_72H", "NOTIFY_COMPLIANCE"]
        return []

    def _determine_ros_destination(self, country: str) -> ROSDestination:
        if country == "UY":
            return ROSDestination.UIAF_UY
        if country == "AR":
            return ROSDestination.UIF_AR
        return ROSDestination.BOTH

    async def _generate_legal_justification(
        self, state: CaseState, verdict: Verdict, score: float,
        multipliers: list[RegulatoryMultiplier], country: str,
    ) -> LegalJustification:
        """Generate detailed legal justification using Claude Opus."""
        try:
            reg = get_regulation.invoke({"country": country, "topic": "all"})

            context = {
                "verdict": verdict.value,
                "score": score,
                "country": country,
                "regulation": reg,
                "multipliers": [m.model_dump() for m in multipliers],
                "sentinel_findings": state.sentinel_report.findings if state.sentinel_report else [],
                "osint_assessment": state.osint_report.identity_assessment if state.osint_report else "N/A",
                "pattern": state.pattern_report.pattern_match.pattern_id if (state.pattern_report and state.pattern_report.pattern_match) else "N/A",
                "fraud_rate": state.historian_report.historical_fraud_rate if state.historian_report else 0,
            }

            prompt = f"""Genera una justificación legal en español formal para el siguiente veredicto de compliance:

{json.dumps(context, default=str, ensure_ascii=False)}

La justificación debe incluir:
1. Normas aplicables (citar artículos específicos)
2. Hechos relevantes
3. Razonamiento jurídico
4. Análisis de proporcionalidad
5. Riesgo de inacción

Responde SOLO con JSON:
{{
    "applicable_norms": ["norma 1", "norma 2"],
    "facts": ["hecho 1", "hecho 2"],
    "reasoning": "...",
    "proportionality": "...",
    "inaction_risk": "..."
}}"""

            response = await self._invoke_llm(JURIST_SYSTEM_PROMPT, prompt)
            content = response.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
            return LegalJustification(**data)
        except Exception as e:
            logger.warning("legal_justification_fallback", error=str(e))
            norms = []
            if country == "UY":
                norms = ["Ley 19.574 Art. 14", "BCU normativa PLA/FT"]
            elif country == "AR":
                norms = ["Ley 25.246 Art. 21 bis", "BCRA Com. A 6399"]

            return LegalJustification(
                applicable_norms=norms + ["GAFI Rec. 20 — Reporte de operaciones sospechosas"],
                facts=[f"Score de confianza: {score:.4f}", f"Veredicto: {verdict.value}"],
                reasoning=f"Basado en el análisis multi-agente, el score de {score:.4f} supera el umbral para {verdict.value}.",
                proportionality=f"La acción de {verdict.value} es proporcional al riesgo identificado.",
                inaction_risk="Riesgo de responsabilidad regulatoria por omisión de reporte según normativa vigente.",
            )
