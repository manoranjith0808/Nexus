"""FastAPI monitoring dashboard for Sentinel Swarm."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from sentinel_swarm.config import get_settings
from sentinel_swarm.models.case import CaseState
from sentinel_swarm.models.events import (
    BankingEvent,
    DeviceReputation,
    EnrichedEvent,
    EventType,
    GeoLocation,
    RecentHistory,
)
from sentinel_swarm.orchestrator.graph import SentinelSwarmOrchestrator
from sentinel_swarm.utils.logging import setup_logging

app = FastAPI(title="Sentinel Swarm — AROS Monitor", version="1.0.0")

# ── In-memory case store ──
_cases: dict[str, dict[str, Any]] = {}
_orchestrator: SentinelSwarmOrchestrator | None = None


def _get_orchestrator() -> SentinelSwarmOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        settings = get_settings()
        setup_logging(settings.log_level)
        _orchestrator = SentinelSwarmOrchestrator()
    return _orchestrator


# ── Request models ──


class EventRequest(BaseModel):
    account_id: str = "ACC-UY-001"
    user_id: str = "USR-001"
    country: str = "UY"
    event_type: str = "transfer"
    amount: float = 15000.0
    currency: str = "USD"
    destination_account: str | None = "ACC-AR-002"
    destination_country: str | None = "AR"
    ip_address: str = "190.64.100.50"
    device_id: str = "DEV-001"
    is_vpn: bool = False
    is_tor: bool = False
    email: str | None = None
    phone: str | None = None
    name: str | None = None
    document_type: str | None = "cedula"
    document_number: str | None = "1.234.567-8"


# ── Endpoints ──


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Interactive monitoring dashboard."""
    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sentinel Swarm — AROS Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'SF Mono', 'Fira Code', monospace; background: #0a0e17; color: #c9d1d9; }
        .header { background: linear-gradient(135deg, #1a1e2e 0%, #0d1117 100%); padding: 20px 30px; border-bottom: 1px solid #30363d; }
        .header h1 { color: #58a6ff; font-size: 1.4em; }
        .header p { color: #8b949e; font-size: 0.85em; margin-top: 4px; }
        .container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 20px; max-width: 1400px; margin: 0 auto; }
        .panel { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }
        .panel h2 { color: #58a6ff; font-size: 1em; margin-bottom: 15px; border-bottom: 1px solid #21262d; padding-bottom: 8px; }
        .full-width { grid-column: 1 / -1; }
        label { display: block; color: #8b949e; font-size: 0.8em; margin: 8px 0 4px; }
        input, select { width: 100%; padding: 8px; background: #0d1117; border: 1px solid #30363d; border-radius: 4px; color: #c9d1d9; font-family: inherit; font-size: 0.85em; }
        .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .row3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
        .checkbox-row { display: flex; gap: 20px; margin-top: 10px; }
        .checkbox-row label { display: flex; align-items: center; gap: 6px; cursor: pointer; }
        .checkbox-row input[type=checkbox] { width: auto; }
        button { padding: 10px 24px; border: none; border-radius: 6px; cursor: pointer; font-family: inherit; font-weight: bold; font-size: 0.9em; margin-top: 15px; }
        .btn-fire { background: #da3633; color: white; }
        .btn-fire:hover { background: #f85149; }
        .btn-fire:disabled { background: #484f58; cursor: not-allowed; }
        .btn-secondary { background: #238636; color: white; }
        .btn-secondary:hover { background: #2ea043; }
        #status { margin-top: 12px; padding: 10px; border-radius: 4px; font-size: 0.85em; display: none; }
        .status-running { background: #1c2333; border: 1px solid #1f6feb; color: #58a6ff; }
        .status-done { background: #1c2d1f; border: 1px solid #238636; color: #3fb950; }
        .status-error { background: #2d1b1b; border: 1px solid #da3633; color: #f85149; }
        .result-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 10px; }
        .agent-card { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 12px; }
        .agent-card h3 { font-size: 0.8em; color: #8b949e; margin-bottom: 6px; }
        .agent-card .score { font-size: 1.8em; font-weight: bold; }
        .score-low { color: #3fb950; }
        .score-mid { color: #d29922; }
        .score-high { color: #f85149; }
        .verdict-badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.85em; font-weight: bold; margin-top: 8px; }
        .verdict-DISCARD { background: #1c2d1f; color: #3fb950; }
        .verdict-MONITOR { background: #2d2a1b; color: #d29922; }
        .verdict-ESCALATE { background: #2d1b1b; color: #f85149; }
        .verdict-BLOCK { background: #5c0a0a; color: #ff7b72; }
        .timeline { margin-top: 10px; }
        .timeline-item { padding: 6px 0; border-left: 2px solid #30363d; padding-left: 12px; margin-left: 8px; font-size: 0.8em; }
        .timeline-item.active { border-left-color: #58a6ff; }
        .timeline-item.done { border-left-color: #3fb950; }
        .meta { color: #8b949e; font-size: 0.75em; }
        .detail-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 0.85em; border-bottom: 1px solid #21262d; }
        .detail-label { color: #8b949e; }
        .cases-list { max-height: 300px; overflow-y: auto; }
        .case-item { padding: 8px; border-bottom: 1px solid #21262d; cursor: pointer; font-size: 0.85em; }
        .case-item:hover { background: #1c2333; }
        .links { margin-top: 15px; }
        .links a { display: inline-block; color: #58a6ff; text-decoration: none; margin-right: 15px; font-size: 0.85em; }
        .links a:hover { text-decoration: underline; }
        .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid #30363d; border-top-color: #58a6ff; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 8px; vertical-align: middle; }
        @keyframes spin { to { transform: rotate(360deg); } }
        pre { background: #0d1117; padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 0.8em; margin-top: 10px; max-height: 400px; overflow-y: auto; border: 1px solid #21262d; }
    </style>
</head>
<body>
    <div class="header">
        <h1>SENTINEL SWARM — AROS Monitor</h1>
        <p>Autonomous Risk Operating System &middot; Real-time Fraud Detection Pipeline</p>
        <div class="links">
            <a href="http://localhost:7474" target="_blank">Neo4j Browser</a>
            <a href="/docs" target="_blank">API Docs (Swagger)</a>
            <a href="/cases" target="_blank">Cases JSON</a>
        </div>
    </div>

    <div class="container">
        <!-- Event Input Panel -->
        <div class="panel">
            <h2>Enviar Evento Bancario</h2>
            <div class="row">
                <div><label>Account ID</label><input id="account_id" value="ACC-UY-001"></div>
                <div><label>User ID</label><input id="user_id" value="USR-001"></div>
            </div>
            <div class="row3">
                <div><label>Tipo</label>
                    <select id="event_type">
                        <option value="transfer">Transfer</option>
                        <option value="login">Login</option>
                        <option value="password_change">Password Change</option>
                        <option value="device_link">Device Link</option>
                        <option value="account_opening">Account Opening</option>
                    </select>
                </div>
                <div><label>País</label>
                    <select id="country">
                        <option value="UY">Uruguay</option>
                        <option value="AR">Argentina</option>
                    </select>
                </div>
                <div><label>Monto (USD)</label><input id="amount" type="number" value="25000"></div>
            </div>
            <div class="row">
                <div><label>Cuenta destino</label><input id="dest_account" value="ACC-AR-002"></div>
                <div><label>País destino</label><input id="dest_country" value="AR"></div>
            </div>
            <div class="row">
                <div><label>IP Address</label><input id="ip_address" value="185.220.101.1"></div>
                <div><label>Device ID</label><input id="device_id" value="DEV-001"></div>
            </div>
            <div class="row">
                <div><label>Email</label><input id="email" value="sospechoso@tempmail.com"></div>
                <div><label>Nombre</label><input id="name" value="Juan Pérez"></div>
            </div>
            <div class="row">
                <div><label>Doc. Tipo</label><input id="doc_type" value="cedula"></div>
                <div><label>Doc. Número</label><input id="doc_number" value="1.234.567-8"></div>
            </div>
            <div class="checkbox-row">
                <label><input type="checkbox" id="is_vpn"> VPN</label>
                <label><input type="checkbox" id="is_tor" checked> TOR</label>
            </div>
            <button class="btn-fire" id="btnSend" onclick="sendEvent()">PROCESAR EVENTO</button>
            <div id="status"></div>
        </div>

        <!-- Results Panel -->
        <div class="panel">
            <h2>Resultado del Pipeline</h2>
            <div id="results">
                <p style="color: #484f58; text-align: center; padding: 40px 0;">Envía un evento para ver los resultados</p>
            </div>
        </div>

        <!-- Agent Details -->
        <div class="panel full-width">
            <h2>Detalle de Agentes</h2>
            <div id="agent-details">
                <p style="color: #484f58; text-align: center; padding: 20px 0;">—</p>
            </div>
        </div>

        <!-- Raw JSON -->
        <div class="panel full-width">
            <h2>JSON Completo del Caso</h2>
            <pre id="raw-json">—</pre>
        </div>
    </div>

<script>
function scoreColor(s) {
    if (s >= 0.65) return 'score-high';
    if (s >= 0.40) return 'score-mid';
    return 'score-low';
}

async function sendEvent() {
    const btn = document.getElementById('btnSend');
    const status = document.getElementById('status');
    btn.disabled = true;
    status.style.display = 'block';
    status.className = 'status-running';
    status.innerHTML = '<span class="spinner"></span> Pipeline en ejecución... (6 agentes)';

    const body = {
        account_id: document.getElementById('account_id').value,
        user_id: document.getElementById('user_id').value,
        country: document.getElementById('country').value,
        event_type: document.getElementById('event_type').value,
        amount: parseFloat(document.getElementById('amount').value),
        currency: 'USD',
        destination_account: document.getElementById('dest_account').value,
        destination_country: document.getElementById('dest_country').value,
        ip_address: document.getElementById('ip_address').value,
        device_id: document.getElementById('device_id').value,
        is_vpn: document.getElementById('is_vpn').checked,
        is_tor: document.getElementById('is_tor').checked,
        email: document.getElementById('email').value || null,
        name: document.getElementById('name').value || null,
        document_type: document.getElementById('doc_type').value || null,
        document_number: document.getElementById('doc_number').value || null,
    };

    try {
        const resp = await fetch('/process', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
        const data = await resp.json();

        status.className = 'status-done';
        status.innerHTML = `✓ Caso ${data.case_id} completado en ${data.total_latency_ms}ms`;

        renderResults(data);
        renderAgentDetails(data);
        document.getElementById('raw-json').textContent = JSON.stringify(data, null, 2);
    } catch (e) {
        status.className = 'status-error';
        status.innerHTML = `✗ Error: ${e.message}`;
    }
    btn.disabled = false;
}

function renderResults(data) {
    const v = data.verdict || 'N/A';
    const s = data.final_confidence_score || 0;
    const agents = [
        { name: 'Centinela', score: data.sentinel_report?.risk_score, detail: data.sentinel_report?.pattern_detected || '—' },
        { name: 'OSINT', score: data.osint_report?.risk_score, detail: data.osint_report?.identity_assessment || '—' },
        { name: 'Patrones', score: data.pattern_report?.risk_score, detail: data.pattern_report?.pattern_match?.pattern_id || '—' },
        { name: 'Historiador', score: data.historian_report?.risk_score, detail: (data.historian_report?.historical_fraud_rate*100||0).toFixed(0) + '% fraud rate' },
        { name: 'Jurista', score: data.jurist_report?.confidence_score, detail: v },
        { name: 'Ejecutor', score: null, detail: data.executor_report?.execution_status || '—' },
    ];

    let html = `<div style="text-align:center; margin-bottom:15px;">
        <div style="font-size:0.8em; color:#8b949e;">VEREDICTO</div>
        <span class="verdict-badge verdict-${v}">${v}</span>
        <div style="margin-top:8px; font-size:2em; font-weight:bold;" class="${scoreColor(s)}">${s.toFixed(4)}</div>
        <div class="meta">${data.total_latency_ms}ms · ${data.status}</div>
    </div>`;

    html += '<div class="result-grid">';
    for (const a of agents) {
        const sc = a.score != null ? a.score.toFixed(4) : '—';
        const cls = a.score != null ? scoreColor(a.score) : '';
        html += `<div class="agent-card"><h3>${a.name}</h3><div class="score ${cls}">${sc}</div><div class="meta">${a.detail}</div></div>`;
    }
    html += '</div>';
    document.getElementById('results').innerHTML = html;
}

function renderAgentDetails(data) {
    let html = '<div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">';

    // Sentinel
    if (data.sentinel_report) {
        const sr = data.sentinel_report;
        html += `<div class="agent-card"><h3>EL CENTINELA</h3>`;
        html += `<div class="detail-row"><span class="detail-label">Patrón</span><span>${sr.pattern_detected || '—'}</span></div>`;
        html += `<div class="detail-row"><span class="detail-label">Risk Score</span><span class="${scoreColor(sr.risk_score)}">${sr.risk_score}</span></div>`;
        if (sr.risk_multipliers_applied) {
            for (const [k,v] of Object.entries(sr.risk_multipliers_applied)) {
                html += `<div class="detail-row"><span class="detail-label">× ${k}</span><span>${v}</span></div>`;
            }
        }
        if (sr.findings?.length) { html += `<div class="meta" style="margin-top:6px">${sr.findings.join('<br>')}</div>`; }
        html += '</div>';
    }

    // OSINT
    if (data.osint_report) {
        const or_ = data.osint_report;
        html += `<div class="agent-card"><h3>INVESTIGADOR OSINT</h3>`;
        html += `<div class="detail-row"><span class="detail-label">Identidad</span><span>${or_.identity_assessment}</span></div>`;
        html += `<div class="detail-row"><span class="detail-label">Legitimacy</span><span>${or_.legitimacy_score}</span></div>`;
        html += `<div class="detail-row"><span class="detail-label">Flags</span><span>${or_.flags?.length || 0}</span></div>`;
        if (or_.flags?.length) { html += `<div class="meta" style="margin-top:6px">${or_.flags.join(', ')}</div>`; }
        html += '</div>';
    }

    // Jurist
    if (data.jurist_report) {
        const jr = data.jurist_report;
        html += `<div class="agent-card"><h3>JURISTA COMPLIANCE</h3>`;
        html += `<div class="detail-row"><span class="detail-label">Veredicto</span><span class="verdict-badge verdict-${jr.verdict}">${jr.verdict}</span></div>`;
        html += `<div class="detail-row"><span class="detail-label">Score</span><span>${jr.confidence_score}</span></div>`;
        html += `<div class="detail-row"><span class="detail-label">ROS</span><span>${jr.ros_required ? '✓ ' + (jr.ros_destination || '') : '—'}</span></div>`;
        if (jr.legal_justification?.applicable_norms?.length) {
            html += `<div class="meta" style="margin-top:6px"><b>Normas:</b> ${jr.legal_justification.applicable_norms.join(', ')}</div>`;
        }
        if (jr.legal_justification?.reasoning) {
            html += `<div class="meta" style="margin-top:4px"><b>Razonamiento:</b> ${jr.legal_justification.reasoning}</div>`;
        }
        html += '</div>';
    }

    // Executor
    if (data.executor_report) {
        const er = data.executor_report;
        html += `<div class="agent-card"><h3>EL EJECUTOR</h3>`;
        html += `<div class="detail-row"><span class="detail-label">Status</span><span>${er.execution_status}</span></div>`;
        html += `<div class="detail-row"><span class="detail-label">Acciones</span><span>${er.actions_executed?.length || 0}</span></div>`;
        if (er.actions_executed?.length) {
            for (const a of er.actions_executed) {
                html += `<div class="detail-row"><span class="detail-label">${a.action}</span><span>${a.status}</span></div>`;
            }
        }
        if (er.ros_generated) {
            html += `<div class="detail-row"><span class="detail-label">ROS ID</span><span>${er.ros_generated.ros_id}</span></div>`;
        }
        html += '</div>';
    }

    html += '</div>';
    document.getElementById('agent-details').innerHTML = html;
}
</script>
</body>
</html>"""


@app.post("/process")
async def process_event(req: EventRequest) -> dict:
    """Process a banking event through the full 6-agent pipeline."""
    event = BankingEvent(
        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
        event_type=EventType(req.event_type),
        timestamp=datetime.now(),
        account_id=req.account_id,
        user_id=req.user_id,
        country=req.country,
        amount=req.amount,
        currency=req.currency,
        destination_account=req.destination_account,
        destination_country=req.destination_country,
        device_id=req.device_id,
        ip_address=req.ip_address,
        document_type=req.document_type,
        document_number=req.document_number,
        metadata={
            "email": req.email,
            "phone": req.phone,
            "name": req.name,
        },
    )

    enriched = EnrichedEvent(
        event=event,
        geo=GeoLocation(
            ip=req.ip_address,
            country="Unknown",
            is_vpn=req.is_vpn,
            is_tor=req.is_tor,
        ),
        device=DeviceReputation(
            device_id=req.device_id,
            known_fraud=False,
            accounts_linked=1,
        ),
        history=RecentHistory(
            events_last_1h=5,
            events_last_24h=12,
            total_amount_24h=req.amount * 2,
        ),
    )

    orchestrator = _get_orchestrator()
    result = await orchestrator.process_event(enriched)

    # Store case
    case_data = result.model_dump(mode="json")
    _cases[result.case_id] = case_data

    return case_data


@app.get("/cases")
async def list_cases() -> list[dict]:
    """List all processed cases."""
    return list(_cases.values())


@app.get("/cases/{case_id}")
async def get_case(case_id: str) -> dict:
    """Get a specific case by ID."""
    if case_id not in _cases:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return _cases[case_id]


@app.get("/health")
async def health() -> dict:
    """Health check."""
    return {
        "status": "ok",
        "cases_processed": len(_cases),
        "timestamp": datetime.now().isoformat(),
    }
