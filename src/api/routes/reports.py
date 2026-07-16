"""Report generation — auto-generates SAR/ROS and case narratives.

Two outputs:
  1. Case narrative (what happened, why it's suspicious, in plain language)
  2. ROS/SAR formal report (regulatory format, exportable)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from sentinel_swarm.api.deps import get_cases_store

router = APIRouter()


def _generate_narrative(c: dict) -> dict:
    """Build a structured narrative from case data — the 'what happened' story."""
    ev = c.get("enriched_event", {})
    evt = ev.get("event", {}) if isinstance(ev, dict) else {}
    sr = c.get("sentinel_report") or {}
    osr = c.get("osint_report") or {}
    pr = c.get("pattern_report") or {}
    hr = c.get("historian_report") or {}
    jr = c.get("jurist_report") or {}
    pm = pr.get("pattern_match") or {}

    account = evt.get("account_id", "—")
    user = evt.get("metadata", {}).get("name") if isinstance(evt.get("metadata"), dict) else None
    user = user or evt.get("user_id", "—")
    amount = evt.get("amount")
    dest = evt.get("destination_account", "—")
    dest_country = evt.get("destination_country", "—")
    ip = evt.get("ip_address", "—")
    device = evt.get("device_id", "—")
    event_type = evt.get("event_type", "—")
    country = evt.get("country", "—")
    score = c.get("final_confidence_score") or 0
    verdict = c.get("verdict") or "—"

    # ── What happened ──
    what_lines = []
    if event_type == "transfer" and amount:
        what_lines.append(f"Se detectó una transferencia de USD {amount:,.2f} desde la cuenta {account} ({country}) hacia {dest} ({dest_country}).")
    elif event_type == "password_change":
        what_lines.append(f"Se registró un cambio de contraseña en la cuenta {account}, potencialmente no autorizado.")
    elif event_type == "device_link":
        what_lines.append(f"Se vinculó un nuevo dispositivo ({device}) a la cuenta {account}.")
    else:
        what_lines.append(f"Se registró actividad de tipo '{event_type}' en la cuenta {account}.")

    what_lines.append(f"El titular asociado es {user}.")

    # ── Why it's suspicious ──
    why_lines = []

    # Pattern
    pattern = pm.get("pattern_id") or sr.get("pattern_detected")
    if pattern and pattern not in ("—", "", "UNKNOWN"):
        pattern_names = {
            "SMURFING": "structuring/smurfing (fragmentación de montos para evadir reportes)",
            "ACCOUNT_TAKEOVER": "toma de cuenta (account takeover) — acceso no autorizado",
            "ROUND_TRIPPING": "round-tripping (transferencias circulares entre entidades relacionadas)",
            "IDENTIDAD_SINTETICA": "identidad sintética (datos fabricados para crear cuentas falsas)",
            "LAYERING": "layering (capas de transacciones para ocultar origen de fondos)",
        }
        why_lines.append(f"El sistema identificó un patrón de **{pattern_names.get(pattern, pattern)}** con {pm.get('similarity_pct', 0):.0f}% de similitud estructural.")

    # Multipliers
    mults = sr.get("risk_multipliers_applied") or {}
    for k, v in mults.items():
        mult_desc = {
            "high_amount": f"Monto superior a USD 10,000 (multiplicador ×{v})",
            "new_account": f"Cuenta con menos de 30 días de antigüedad (×{v})",
            "vpn_tor": f"Conexión desde VPN/TOR (×{v})",
            "gafi_high_risk": f"Destino en jurisdicción de alto riesgo GAFI (×{v})",
        }
        why_lines.append(mult_desc.get(k, f"Factor de riesgo: {k} (×{v})"))

    # OSINT
    ia = osr.get("identity_assessment", "")
    if ia == "SYNTHETIC_PROBABLE":
        why_lines.append("La validación OSINT indica alta probabilidad de **identidad sintética** — sin huella digital legítima encontrada.")
    elif ia == "UNVERIFIED":
        why_lines.append("No fue posible verificar la identidad del titular a través de fuentes externas.")

    # Shared resources
    suspect_nodes = sr.get("suspect_nodes") or []
    if len(suspect_nodes) > 2:
        why_lines.append(f"Se detectaron {len(suspect_nodes)} cuentas vinculadas al mismo dispositivo o IP, indicador de actividad coordinada.")

    # Historian
    fraud_rate = hr.get("historical_fraud_rate", 0)
    prec_count = hr.get("precedent_count", 0)
    if fraud_rate > 0.5 and prec_count > 2:
        why_lines.append(f"De {prec_count} casos históricos similares, el {fraud_rate:.0%} fueron confirmados como fraude.")

    if not why_lines:
        why_lines.append("Múltiples indicadores de riesgo activaron el sistema de detección automática.")

    # ── Recommendation ──
    rec_map = {
        "BLOCK": "**Bloqueo inmediato** de la cuenta y cancelación de la transacción. Generación de ROS obligatorio.",
        "ESCALATE": "**Escalamiento** a oficial de compliance senior para revisión prioritaria. Recomendación de bloqueo preventivo.",
        "MONITOR": "**Monitoreo intensivo** por 72 horas. No se recomienda bloqueo inmediato pero sí seguimiento de actividad subsiguiente.",
    }
    recommendation = rec_map.get(verdict, "Revisión manual recomendada.")

    # ── Rules triggered ──
    rules = []
    if amount and amount > 10000:
        rules.append({"rule": "HIGH_AMOUNT", "desc": f"Monto > USD 10,000 (USD {amount:,.0f})", "severity": "HIGH"})
    geo = ev.get("geo") or {}
    if isinstance(geo, dict):
        if geo.get("is_tor"):
            rules.append({"rule": "TOR_NETWORK", "desc": "Conexión desde red TOR", "severity": "CRITICAL"})
        if geo.get("is_vpn"):
            rules.append({"rule": "VPN_DETECTED", "desc": "IP identificada como VPN", "severity": "HIGH"})
    if ia in ("SYNTHETIC_PROBABLE", "UNVERIFIED"):
        rules.append({"rule": "IDENTITY_RISK", "desc": f"Identidad: {ia}", "severity": "CRITICAL" if ia == "SYNTHETIC_PROBABLE" else "HIGH"})
    if pattern and pattern not in ("—", "", "UNKNOWN"):
        rules.append({"rule": "PATTERN_MATCH", "desc": f"Patrón: {pattern} ({pm.get('similarity_pct',0):.0f}%)", "severity": "HIGH"})
    if fraud_rate > 0.5:
        rules.append({"rule": "HISTORICAL_MATCH", "desc": f"{fraud_rate:.0%} de precedentes fueron fraude", "severity": "MEDIUM"})

    return {
        "summary": what_lines[0],
        "what_happened": what_lines,
        "why_suspicious": why_lines,
        "recommendation": recommendation,
        "rules_triggered": rules,
        "entities": {
            "account": account,
            "user": user,
            "ip": ip,
            "device": device,
            "destination": dest,
            "destination_country": dest_country,
        },
        "score": score,
        "verdict": verdict,
    }


def _generate_ros(c: dict, narrative: dict) -> dict:
    """Generate a formal ROS/SAR report."""
    ev = c.get("enriched_event", {})
    evt = ev.get("event", {}) if isinstance(ev, dict) else {}
    jr = c.get("jurist_report") or {}
    country = evt.get("country") or c.get("country", "UY")

    now = datetime.utcnow().isoformat()

    # Determine regulatory body
    if country == "UY":
        regulator = "UIAF — Unidad de Información y Análisis Financiero"
        framework = "Ley 19.574 (Uruguay), normativa BCU/SENACLAFT"
        report_type = "Reporte de Operación Sospechosa (ROS)"
    else:
        regulator = "UIF — Unidad de Información Financiera"
        framework = "Ley 25.246/26.683 (Argentina), Com. A 6399 BCRA"
        report_type = "Reporte de Operación Sospechosa (ROS)"

    ent = narrative["entities"]

    return {
        "report_id": f"ROS-{c.get('case_id', '')[5:]}",
        "report_type": report_type,
        "regulator": regulator,
        "legal_framework": framework,
        "generated_at": now,
        "case_id": c.get("case_id", ""),

        "subject": {
            "name": ent["user"],
            "account": ent["account"],
            "document": evt.get("document_number", "—"),
            "document_type": evt.get("document_type", "—"),
            "country": country,
        },

        "operation": {
            "type": evt.get("event_type", "—"),
            "amount": evt.get("amount"),
            "currency": evt.get("currency", "USD"),
            "destination_account": ent["destination"],
            "destination_country": ent["destination_country"],
            "date": evt.get("timestamp", now),
            "channel": evt.get("channel", "digital"),
        },

        "suspicion_grounds": narrative["why_suspicious"],
        "rules_triggered": narrative["rules_triggered"],
        "system_score": narrative["score"],
        "system_verdict": narrative["verdict"],
        "recommendation": narrative["recommendation"],

        "supporting_evidence": {
            "ip_address": ent["ip"],
            "device_id": ent["device"],
            "pattern_detected": narrative.get("rules_triggered", [{}])[0].get("desc", "—") if narrative.get("rules_triggered") else "—",
        },

        "action_taken": "Bloqueo preventivo" if narrative["verdict"] == "BLOCK" else "Monitoreo intensivo" if narrative["verdict"] == "MONITOR" else "Escalado a compliance senior",
    }


# ── Endpoints ──


@router.get("/{case_id}/narrative")
async def get_narrative(case_id: str) -> dict:
    """Get the auto-generated case narrative — plain language 'what happened and why'."""
    store = get_cases_store()
    c = store.get(case_id)
    if not c:
        raise HTTPException(404, f"Case {case_id} not found")
    return _generate_narrative(c)


@router.get("/{case_id}/ros")
async def get_ros(case_id: str) -> dict:
    """Get the auto-generated ROS/SAR report in structured format."""
    store = get_cases_store()
    c = store.get(case_id)
    if not c:
        raise HTTPException(404, f"Case {case_id} not found")
    narrative = _generate_narrative(c)
    return _generate_ros(c, narrative)


@router.get("/{case_id}/ros/html", response_class=HTMLResponse)
async def get_ros_html(case_id: str) -> str:
    """Get the ROS as printable/exportable HTML (for PDF conversion)."""
    store = get_cases_store()
    c = store.get(case_id)
    if not c:
        raise HTTPException(404, f"Case {case_id} not found")

    narrative = _generate_narrative(c)
    ros = _generate_ros(c, narrative)
    s = ros["subject"]
    o = ros["operation"]

    rules_html = "".join(f"<tr><td>{r['rule']}</td><td>{r['desc']}</td><td>{r['severity']}</td></tr>" for r in ros.get("rules_triggered", []))
    grounds_html = "".join(f"<li>{g}</li>" for g in ros.get("suspicion_grounds", []))

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
@page {{ size: A4; margin: 2cm; }}
body {{ font-family: 'Times New Roman', serif; font-size: 12pt; line-height: 1.6; color: #1a1a1a; max-width: 800px; margin: 0 auto; padding: 40px; }}
h1 {{ font-size: 16pt; text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; }}
h2 {{ font-size: 13pt; margin-top: 24px; border-bottom: 1px solid #ccc; padding-bottom: 4px; color: #333; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
td, th {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 11pt; }}
th {{ background: #f5f5f5; font-weight: bold; }}
.header {{ text-align: center; margin-bottom: 30px; }}
.header .report-id {{ font-size: 10pt; color: #666; }}
.confidential {{ text-align: center; color: #c00; font-weight: bold; font-size: 10pt; margin: 10px 0; }}
.footer {{ margin-top: 40px; font-size: 9pt; color: #666; border-top: 1px solid #ddd; padding-top: 10px; }}
.score {{ font-size: 18pt; font-weight: bold; color: {'#c00' if ros['system_score'] >= .65 else '#e60' if ros['system_score'] >= .4 else '#090'}; }}
</style></head><body>
<div class="confidential">CONFIDENCIAL — USO EXCLUSIVO COMPLIANCE</div>
<div class="header">
<h1>{ros['report_type']}</h1>
<div class="report-id">{ros['report_id']} · {ros['generated_at'][:10]}</div>
<div style="font-size:10pt;color:#666;">Dirigido a: {ros['regulator']}</div>
<div style="font-size:10pt;color:#666;">Marco legal: {ros['legal_framework']}</div>
</div>

<h2>1. Datos del sujeto reportado</h2>
<table><tr><th>Nombre</th><td>{s['name']}</td></tr>
<tr><th>Cuenta</th><td>{s['account']}</td></tr>
<tr><th>Documento</th><td>{s['document_type']} {s['document']}</td></tr>
<tr><th>País</th><td>{s['country']}</td></tr></table>

<h2>2. Descripción de la operación</h2>
<table><tr><th>Tipo</th><td>{o['type']}</td></tr>
<tr><th>Monto</th><td>{o['currency']} {o['amount']:,.2f}</td></tr>
<tr><th>Destino</th><td>{o['destination_account']} ({o['destination_country']})</td></tr>
<tr><th>Fecha</th><td>{o['date'][:19]}</td></tr>
<tr><th>Canal</th><td>{o['channel']}</td></tr></table>

<h2>3. Fundamentos de la sospecha</h2>
<ul>{grounds_html}</ul>

<h2>4. Reglas del sistema activadas</h2>
<table><tr><th>Regla</th><th>Descripción</th><th>Severidad</th></tr>{rules_html}</table>

<h2>5. Evaluación del sistema</h2>
<p>Score de confianza: <span class="score">{ros['system_score']:.4f}</span></p>
<p>Veredicto automático: <strong>{ros['system_verdict']}</strong></p>
<p>Recomendación: {ros['recommendation']}</p>

<h2>6. Evidencia de respaldo</h2>
<table><tr><th>IP de origen</th><td>{ros['supporting_evidence']['ip_address']}</td></tr>
<tr><th>Dispositivo</th><td>{ros['supporting_evidence']['device_id']}</td></tr>
<tr><th>Patrón</th><td>{ros['supporting_evidence']['pattern_detected']}</td></tr></table>

<h2>7. Acción tomada</h2>
<p>{ros['action_taken']}</p>

<div class="footer">
Generado automáticamente por Sentinel Swarm AROS · Caso {ros['case_id']}<br>
Este documento es confidencial y está destinado exclusivamente al regulador indicado.
</div></body></html>"""
