"""Agent 6 — El Ejecutor (The Executor): Core banking actions and ROS generation."""

from __future__ import annotations

import json
import time

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from tenacity import retry, stop_after_attempt, wait_fixed

from sentinel_swarm.agents.base import BaseAgent
from sentinel_swarm.config import get_settings
from sentinel_swarm.models.agents import (
    ActionResult,
    ExecutorReport,
    ROSDestination,
    ROSDocument,
    Verdict,
)
from sentinel_swarm.models.case import CaseState
from sentinel_swarm.tools.execution_tools import (
    block_account,
    cancel_transaction,
    generate_ros,
    notify_client,
    notify_compliance,
    submit_ros,
    update_graph_status,
)

logger = structlog.get_logger("agents.executor")

EXECUTOR_SYSTEM_PROMPT = """Eres El Ejecutor (The Executor), el ÚNICO agente con permisos de escritura sobre el core bancario en el sistema Sentinel Swarm.

## Secuencia de ejecución:

1. Validación pre-ejecución (verificar que el veredicto es válido y las acciones son coherentes)
2. Bloqueo de cuenta (si ordenado)
3. Cancelación/contracargo de transacción (si ordenada)
4. Generación de ROS (Reporte de Operación Sospechosa)
5. Notificación interna a compliance
6. Actualización del grafo (etiquetas BLOCKED_FRAUD, UNDER_INVESTIGATION)
7. Notificación genérica al cliente (anti-tipping-off — NO revelar motivo)

## ROS — Reporte de Operación Sospechosa:

El ROS debe contener:
- Datos del sujeto reportado
- Descripción detallada de la operación
- Fundamentos de la sospecha
- Documentación de respaldo
- Acción tomada por el banco

Formato según regulador:
- Uruguay → SENACLAFT (UIAF)
- Argentina → UIF electrónico (Res. 30/2017)

Idioma: español formal rioplatense.

## Anti-tipping-off:

La notificación al cliente NUNCA debe revelar:
- Que existe una investigación
- Que se reportó un ROS
- Los motivos específicos de la restricción

Solo mensajes genéricos de seguridad.
"""

ESCRIBANO_PROMPT = """Eres El Escribano, un sub-agente del Ejecutor especializado en generar Reportes de Operación Sospechosa (ROS).

Genera el ROS en español formal rioplatense con la siguiente estructura:

1. DATOS DEL SUJETO REPORTADO
2. DESCRIPCIÓN DE LA OPERACIÓN
3. FUNDAMENTOS DE LA SOSPECHA
4. DOCUMENTACIÓN DE RESPALDO
5. ACCIÓN TOMADA POR LA ENTIDAD

El ROS debe ser claro, conciso, y cumplir con los requisitos formales del regulador ({regulator}).
"""


class ExecutorAgent(BaseAgent):
    """Agent 6 — El Ejecutor: Core banking write operations."""

    agent_id = "executor"
    description = "El Ejecutor — Ejecución de acciones sobre el core bancario (único con permisos de escritura)."

    def __init__(self, llm: BaseChatModel) -> None:
        tools: list[BaseTool] = [
            block_account,
            cancel_transaction,
            generate_ros,
            submit_ros,
            notify_compliance,
            update_graph_status,
            notify_client,
        ]
        super().__init__(llm, tools)

    async def _execute(self, state: CaseState) -> CaseState:
        start = time.monotonic()
        settings = get_settings()

        if not state.jurist_report:
            state.error_log.append("executor: no jurist report — cannot execute")
            return state

        verdict = state.jurist_report.verdict
        actions_ordered = state.jurist_report.actions_ordered
        event = state.enriched_event
        if not event:
            state.error_log.append("executor: no enriched event")
            return state

        account_id = event.event.account_id
        case_id = state.case_id
        country = event.event.country

        actions_executed: list[ActionResult] = []
        errors: list[str] = []
        notifications: list[str] = []
        ros_doc: ROSDocument | None = None

        # ── Step 1: Validation ──
        if verdict == Verdict.DISCARD:
            latency_ms = int((time.monotonic() - start) * 1000)
            state.executor_report = ExecutorReport(
                case_id=case_id,
                risk_score=state.final_confidence_score or 0.0,
                confidence=1.0,
                execution_status="SKIPPED",
                actions_executed=[ActionResult(
                    action="VALIDATION", status="SKIPPED",
                    details="Verdict is DISCARD — no actions required",
                )],
                latency_ms=latency_ms,
            )
            return state

        # ── Step 2: Block account ──
        if "BLOCK_ACCOUNT" in actions_ordered:
            result = await self._execute_with_retry(
                block_account, account_id=account_id, reason=f"Fraud verdict: {verdict.value}", case_id=case_id
            )
            actions_executed.append(ActionResult(
                action="BLOCK_ACCOUNT",
                status=result.get("status", "FAILED"),
                rollback_id=result.get("rollback_id"),
                details=f"Account {account_id} blocked",
            ))
            if result.get("status") != "SUCCESS":
                errors.append(f"Account block failed: {result}")

        # ── Step 3: Cancel transaction ──
        if "CANCEL_TRANSACTION" in actions_ordered and event.event.event_type == "transfer":
            result = await self._execute_with_retry(
                cancel_transaction, tx_id=event.event.event_id, reason="Fraud prevention", case_id=case_id
            )
            actions_executed.append(ActionResult(
                action="CANCEL_TRANSACTION",
                status=result.get("status", "FAILED"),
                rollback_id=result.get("rollback_id"),
                details=f"Transaction {event.event.event_id} cancelled",
            ))

        # ── Step 4: Generate ROS ──
        if "GENERATE_ROS" in actions_ordered and state.jurist_report.ros_required:
            ros_content = await self._generate_ros_content(state)
            ros_result = generate_ros.invoke({
                "case_id": case_id,
                "country": country,
                "subject_name": event.event.metadata.get("name", event.event.user_id),
                "subject_document": event.event.document_number or "N/A",
                "operation_description": ros_content.get("operation_description", ""),
                "suspicion_grounds": ros_content.get("suspicion_grounds", ""),
                "action_taken": ros_content.get("action_taken", ""),
            })

            ros_destination = state.jurist_report.ros_destination or ROSDestination.UIAF_UY
            ros_doc = ROSDocument(
                ros_id=ros_result.get("ros_id", ""),
                destination=ros_destination,
                subject_data=ros_result.get("subject", {}),
                operation_description=ros_result.get("operation_description", ""),
                suspicion_grounds=ros_result.get("suspicion_grounds", ""),
                action_taken=ros_result.get("action_taken", ""),
            )

            actions_executed.append(ActionResult(
                action="GENERATE_ROS",
                status="SUCCESS",
                details=f"ROS {ros_doc.ros_id} generated for {ros_destination}",
            ))

            # Auto-submit if configured
            if settings.ros_auto_submit:
                submit_result = submit_ros.invoke({
                    "ros_id": ros_doc.ros_id,
                    "destination": ros_destination.value,
                })
                actions_executed.append(ActionResult(
                    action="SUBMIT_ROS",
                    status=submit_result.get("status", "FAILED"),
                    details=f"ROS submitted, confirmation: {submit_result.get('confirmation_number', 'N/A')}",
                ))

        # ── Step 5: Notify compliance ──
        if "NOTIFY_COMPLIANCE" in actions_ordered:
            summary = self._build_compliance_summary(state)
            notif_result = notify_compliance.invoke({
                "case_id": case_id,
                "verdict": verdict.value,
                "summary": summary,
                "urgency": "CRITICAL" if verdict == Verdict.BLOCK else "HIGH",
            })
            notifications.append(f"Compliance: {notif_result.get('notification_id')}")
            actions_executed.append(ActionResult(
                action="NOTIFY_COMPLIANCE",
                status=notif_result.get("status", "FAILED"),
                details=summary[:200],
            ))

        # ── Step 6: Update graph ──
        graph_updated = False
        if verdict in (Verdict.BLOCK, Verdict.ESCALATE):
            labels = []
            status = "ACTIVE"
            if verdict == Verdict.BLOCK:
                labels = ["BLOCKED_FRAUD"]
                status = "BLOCKED_FRAUD"
            elif verdict == Verdict.ESCALATE:
                labels = ["UNDER_INVESTIGATION"]
                status = "UNDER_INVESTIGATION"

            graph_result = update_graph_status.invoke({
                "account_id": account_id,
                "status": status,
                "labels": labels,
            })
            graph_updated = graph_result.get("result") == "SUCCESS"
            actions_executed.append(ActionResult(
                action="UPDATE_GRAPH",
                status="SUCCESS" if graph_updated else "FAILED",
                details=f"Graph updated: status={status}, labels={labels}",
            ))

        # ── Step 7: Notify client (anti-tipping-off) ──
        if "NOTIFY_CLIENT" in actions_ordered:
            client_notif = notify_client.invoke({
                "account_id": account_id,
                "notification_type": "generic_security",
            })
            notifications.append(f"Client: {client_notif.get('notification_id')}")
            actions_executed.append(ActionResult(
                action="NOTIFY_CLIENT",
                status=client_notif.get("status", "FAILED"),
                details="Generic security notification sent (anti-tipping-off compliant)",
            ))

        latency_ms = int((time.monotonic() - start) * 1000)

        report = ExecutorReport(
            case_id=case_id,
            risk_score=state.final_confidence_score or 0.0,
            confidence=1.0,
            execution_status="COMPLETED" if not errors else "PARTIAL",
            actions_executed=actions_executed,
            ros_generated=ros_doc,
            notifications_sent=notifications,
            graph_updated=graph_updated,
            errors=errors,
            findings=[f"Executed {len(actions_executed)} actions for verdict {verdict.value}"],
            recommendation=f"Execution {'complete' if not errors else 'partial — check errors'}",
            latency_ms=latency_ms,
        )

        state.executor_report = report
        return state

    async def _execute_with_retry(self, tool_fn, **kwargs) -> dict:
        """Execute a tool with up to 3 retries."""
        last_error = None
        for attempt in range(3):
            try:
                return tool_fn.invoke(kwargs)
            except Exception as e:
                last_error = e
                logger.warning(
                    "execution_retry",
                    tool=tool_fn.name,
                    attempt=attempt + 1,
                    error=str(e),
                )
        logger.error("execution_failed_all_retries", tool=tool_fn.name, error=str(last_error))
        return {"status": "FAILED", "error": str(last_error)}

    async def _generate_ros_content(self, state: CaseState) -> dict:
        """Use the Escribano sub-agent (Claude Opus) to generate ROS content."""
        event = state.enriched_event
        assert event is not None
        country = event.event.country
        regulator = "SENACLAFT/UIAF" if country == "UY" else "UIF (Res. 30/2017)"

        try:
            context = {
                "case_id": state.case_id,
                "account": event.event.account_id,
                "user": event.event.user_id,
                "document": f"{event.event.document_type} {event.event.document_number}",
                "event_type": event.event.event_type,
                "amount": event.event.amount,
                "currency": event.event.currency,
                "sentinel_findings": state.sentinel_report.findings if state.sentinel_report else [],
                "osint_assessment": state.osint_report.identity_assessment if state.osint_report else "N/A",
                "pattern": state.pattern_report.pattern_match.pattern_id if (state.pattern_report and state.pattern_report.pattern_match) else "N/A",
                "verdict": state.verdict.value if state.verdict else "N/A",
                "score": state.final_confidence_score,
            }

            prompt = f"""Genera el contenido del ROS (Reporte de Operación Sospechosa) para el regulador {regulator}.

Contexto del caso:
{json.dumps(context, default=str, ensure_ascii=False)}

Responde con JSON:
{{
    "operation_description": "Descripción detallada de la operación en español formal rioplatense",
    "suspicion_grounds": "Fundamentos de la sospecha basados en la evidencia recolectada",
    "action_taken": "Acción tomada por la entidad financiera"
}}"""

            response = await self._invoke_llm(
                ESCRIBANO_PROMPT.format(regulator=regulator), prompt
            )
            content = response.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except Exception as e:
            logger.warning("ros_generation_fallback", error=str(e))
            return {
                "operation_description": (
                    f"Operación de tipo {event.event.event_type} por cuenta {event.event.account_id}, "
                    f"monto {event.event.amount} {event.event.currency or 'USD'}."
                ),
                "suspicion_grounds": (
                    f"Score de riesgo: {state.final_confidence_score}. "
                    f"Veredicto del sistema: {state.verdict.value if state.verdict else 'N/A'}."
                ),
                "action_taken": f"Bloqueo preventivo de cuenta y generación de ROS según normativa vigente.",
            }

    def _build_compliance_summary(self, state: CaseState) -> str:
        """Build a summary for the compliance notification."""
        parts = [f"Case {state.case_id} — Verdict: {state.verdict.value if state.verdict else 'N/A'}"]
        parts.append(f"Confidence Score: {state.final_confidence_score}")
        if state.sentinel_report:
            parts.append(f"Pattern: {state.sentinel_report.pattern_detected}")
        if state.osint_report:
            parts.append(f"Identity: {state.osint_report.identity_assessment}")
        if state.jurist_report and state.jurist_report.ros_required:
            dest = state.jurist_report.ros_destination
            parts.append(f"ROS required → {dest.value if dest else 'TBD'}")
        return " | ".join(parts)
