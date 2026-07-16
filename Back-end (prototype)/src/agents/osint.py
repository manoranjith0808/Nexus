"""Agent 2 — El Investigador OSINT (The Stalker): External identity validation."""

from __future__ import annotations

import json
import time

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from sentinel_swarm.agents.base import BaseAgent
from sentinel_swarm.models.agents import (
    IdentityAssessment,
    OSINTFlag,
    OSINTReport,
)
from sentinel_swarm.models.case import CaseState
from sentinel_swarm.tools.osint_tools import (
    breach_check,
    device_intelligence,
    ip_reputation,
    phone_intelligence,
    verify_email,
    web_search_osint,
)

logger = structlog.get_logger("agents.osint")

# Flag penalties
FLAG_PENALTIES: dict[str, float] = {
    "FLAG_NEW_EMAIL": 0.15,
    "FLAG_DISPOSABLE": 0.30,
    "FLAG_NO_FOOTPRINT": 0.20,
    "FLAG_SIM_SWAP": 0.25,
    "FLAG_VPN": 0.10,
    "FLAG_TOR": 0.20,
    "FLAG_KNOWN_FRAUD_DEVICE": 0.30,
    "FLAG_SYNTHETIC_IDENTITY_PROBABLE": 0.25,
    "FLAG_HIGH_ABUSE_IP": 0.20,
    "FLAG_BREACHED_EMAIL": 0.10,
    "FLAG_EMULATOR": 0.15,
    "FLAG_ROOTED_DEVICE": 0.10,
    "FLAG_MULTIPLE_ACCOUNTS": 0.20,
}

OSINT_SYSTEM_PROMPT = """Eres El Investigador OSINT (The Stalker), el agente de validación externa de identidad del sistema Sentinel Swarm.

Tu misión es validar la identidad de personas sospechosas usando fuentes abiertas y APIs especializadas.

## Proceso de investigación (5 pasos):

1. **Verificación de email**: Antigüedad, proveedor (disposable?), presencia en redes (LinkedIn, GitHub).
2. **Huella del teléfono**: Antigüedad de línea, portabilidad, SIM swap reciente.
3. **Reputación de IP y dispositivo**: AbuseIPDB, MaxMind, blacklists, emuladores, rooted.
4. **Búsqueda en filtraciones**: Have I Been Pwned.
5. **Análisis de coherencia**: Cruzar todos los datos para evaluar si la identidad es coherente.

## Sistema de flags con penalizaciones:

- FLAG_NEW_EMAIL: -0.15 (email < 30 días)
- FLAG_DISPOSABLE: -0.30 (email de servicio descartable)
- FLAG_NO_FOOTPRINT: -0.20 (sin presencia social)
- FLAG_SIM_SWAP: -0.25 (SIM swap en últimos 30 días)
- FLAG_VPN: -0.10 (conexión VPN)
- FLAG_TOR: -0.20 (red TOR)
- FLAG_KNOWN_FRAUD_DEVICE: -0.30 (dispositivo en lista de fraude)
- FLAG_SYNTHETIC_IDENTITY_PROBABLE: -0.25 (probable identidad sintética)

## Cálculo:

legitimacy_score empieza en 1.0, se resta por cada flag. risk_score = 1.0 - legitimacy_score.

## Output:

Responde ÚNICAMENTE con JSON:
{
    "identity_assessment": "VERIFIED|PARTIALLY_VERIFIED|UNVERIFIED|SYNTHETIC_PROBABLE",
    "legitimacy_score": float,
    "flags": [{"flag_id": "...", "description": "...", "penalty": float}],
    "narrative_summary": "Resumen en español de los hallazgos",
    "email_verified": bool,
    "phone_verified": bool
}
"""


class OSINTAgent(BaseAgent):
    """Agent 2 — El Investigador OSINT: External identity validation."""

    agent_id = "osint"
    description = "El Investigador OSINT — Validación externa de identidad."

    def __init__(self, llm: BaseChatModel) -> None:
        tools: list[BaseTool] = [
            verify_email,
            phone_intelligence,
            ip_reputation,
            device_intelligence,
            breach_check,
            web_search_osint,
        ]
        super().__init__(llm, tools)

    async def _execute(self, state: CaseState) -> CaseState:
        start = time.monotonic()
        event = state.enriched_event
        if not event:
            state.error_log.append("osint: no enriched event")
            return state

        collected_flags: list[OSINTFlag] = []
        legitimacy_score = 1.0

        # ── Step 1: Email verification ──
        email = event.event.metadata.get("email")
        email_verified = None
        if email:
            email_result = verify_email.invoke({"email": email})
            email_verified = email_result.get("exists", False)
            for flag_id in email_result.get("flags", []):
                penalty = FLAG_PENALTIES.get(flag_id, 0.10)
                collected_flags.append(OSINTFlag(
                    flag_id=flag_id, description=f"Email check: {flag_id}", penalty=penalty, source="email"
                ))
                legitimacy_score -= penalty

        # ── Step 2: Phone intelligence ──
        phone = event.event.metadata.get("phone")
        phone_verified = None
        if phone:
            phone_result = phone_intelligence.invoke({"phone_number": phone})
            phone_verified = not phone_result.get("sim_swap_recent", False)
            if phone_result.get("sim_swap_recent"):
                collected_flags.append(OSINTFlag(
                    flag_id="FLAG_SIM_SWAP", description="SIM swap detected in last 30 days",
                    penalty=0.25, source="phone",
                ))
                legitimacy_score -= 0.25
            for flag_id in phone_result.get("flags", []):
                penalty = FLAG_PENALTIES.get(flag_id, 0.10)
                collected_flags.append(OSINTFlag(
                    flag_id=flag_id, description=f"Phone check: {flag_id}", penalty=penalty, source="phone"
                ))
                legitimacy_score -= penalty

        # ── Step 3: IP + Device reputation ──
        if event.event.ip_address:
            ip_result = ip_reputation.invoke({"ip_address": event.event.ip_address})
            for flag_id in ip_result.get("flags", []):
                penalty = FLAG_PENALTIES.get(flag_id, 0.10)
                collected_flags.append(OSINTFlag(
                    flag_id=flag_id, description=f"IP check: {flag_id}", penalty=penalty, source="ip"
                ))
                legitimacy_score -= penalty

            # Also check VPN/TOR from enrichment
            if event.geo and event.geo.is_vpn:
                collected_flags.append(OSINTFlag(
                    flag_id="FLAG_VPN", description="VPN connection detected",
                    penalty=0.10, source="geo",
                ))
                legitimacy_score -= 0.10
            if event.geo and event.geo.is_tor:
                collected_flags.append(OSINTFlag(
                    flag_id="FLAG_TOR", description="TOR network detected",
                    penalty=0.20, source="geo",
                ))
                legitimacy_score -= 0.20

        if event.event.device_id:
            device_result = device_intelligence.invoke({"device_id": event.event.device_id})
            if device_result.get("known_fraud"):
                collected_flags.append(OSINTFlag(
                    flag_id="FLAG_KNOWN_FRAUD_DEVICE", description="Device linked to prior fraud",
                    penalty=0.30, source="device",
                ))
                legitimacy_score -= 0.30
            if device_result.get("is_emulator"):
                collected_flags.append(OSINTFlag(
                    flag_id="FLAG_EMULATOR", description="Device is an emulator",
                    penalty=0.15, source="device",
                ))
                legitimacy_score -= 0.15
            if device_result.get("accounts_linked", 0) > 3:
                collected_flags.append(OSINTFlag(
                    flag_id="FLAG_MULTIPLE_ACCOUNTS",
                    description=f"Device linked to {device_result['accounts_linked']} accounts",
                    penalty=0.20, source="device",
                ))
                legitimacy_score -= 0.20

        # ── Step 4: Breach check ──
        if email:
            breach_result = breach_check.invoke({"email": email})
            if breach_result.get("breached"):
                collected_flags.append(OSINTFlag(
                    flag_id="FLAG_BREACHED_EMAIL",
                    description=f"Email found in {breach_result.get('breach_count', 0)} breaches",
                    penalty=0.10, source="breach",
                ))
                legitimacy_score -= 0.10

        # ── Step 5: Coherence analysis via LLM ──
        legitimacy_score = max(legitimacy_score, 0.0)
        risk_score = round(1.0 - legitimacy_score, 4)

        # Determine identity assessment
        if legitimacy_score >= 0.80:
            assessment = IdentityAssessment.VERIFIED
        elif legitimacy_score >= 0.60:
            assessment = IdentityAssessment.PARTIALLY_VERIFIED
        elif legitimacy_score >= 0.35:
            assessment = IdentityAssessment.UNVERIFIED
        else:
            assessment = IdentityAssessment.SYNTHETIC_PROBABLE

        # LLM narrative summary
        narrative = await self._generate_narrative(
            event, collected_flags, legitimacy_score, assessment
        )

        latency_ms = int((time.monotonic() - start) * 1000)

        report = OSINTReport(
            case_id=state.case_id,
            risk_score=risk_score,
            confidence=round(min(0.5 + len(collected_flags) * 0.08, 0.95), 2),
            identity_assessment=assessment,
            legitimacy_score=round(legitimacy_score, 4),
            osint_flags=collected_flags,
            narrative_summary=narrative,
            email_verified=email_verified,
            phone_verified=phone_verified,
            ip_reputation_score=None,
            findings=[f.description for f in collected_flags],
            flags=[f.flag_id for f in collected_flags],
            recommendation=f"Identity assessment: {assessment.value}",
            latency_ms=latency_ms,
        )

        state.osint_report = report
        return state

    async def _generate_narrative(
        self, event, flags: list[OSINTFlag], legitimacy: float, assessment: IdentityAssessment
    ) -> str:
        """Generate a narrative summary using the LLM."""
        try:
            flags_text = "\n".join(f"- {f.flag_id}: {f.description} (penalización: {f.penalty})" for f in flags)
            prompt = f"""Genera un resumen narrativo en español de la investigación OSINT:

Cuenta: {event.event.account_id}
Usuario: {event.event.user_id}
País: {event.event.country}
Flags detectados:
{flags_text}

Legitimacy score: {legitimacy}
Assessment: {assessment.value}

Escribe un párrafo conciso explicando los hallazgos y su implicancia para el perfil de riesgo."""

            return await self._invoke_llm(OSINT_SYSTEM_PROMPT, prompt)
        except Exception as e:
            logger.warning("narrative_generation_failed", error=str(e))
            flag_summary = ", ".join(f.flag_id for f in flags)
            return (
                f"Investigación OSINT completada. Assessment: {assessment.value}. "
                f"Legitimacy score: {legitimacy}. Flags: {flag_summary or 'ninguno'}."
            )
