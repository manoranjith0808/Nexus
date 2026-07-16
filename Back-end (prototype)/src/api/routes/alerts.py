"""Alert management — the core workflow for compliance analysts.

Alerts are cases that need human review. They flow through:
PENDING → REVIEWING → APPROVED/REJECTED/ESCALATED

Each state transition is logged in an audit trail.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from sentinel_swarm.api.deps import get_cases_store

router = APIRouter()


# ── Models ──

class Decision(BaseModel):
    action: str = Field(..., pattern=r"^(APPROVE|REJECT|ESCALATE)$")
    analyst_id: str
    analyst_name: str = ""
    reason: str = ""
    notes: str = ""


class AlertSummary(BaseModel):
    case_id: str
    alert_status: str  # PENDING, REVIEWING, APPROVED, REJECTED, ESCALATED
    verdict: str
    score: float
    pattern: str
    account_id: str
    user_name: str
    amount: float | None
    country: str
    created_at: str
    latency_ms: int
    tenant_id: str
    tenant_name: str


# ── Helpers ──

def _extract_alert(c: dict, tenants_map: dict) -> dict:
    """Extract alert-relevant fields from a raw case."""
    ev = c.get("enriched_event", {})
    evt = ev.get("event", {}) if isinstance(ev, dict) else {}
    sr = c.get("sentinel_report") or {}
    pr = c.get("pattern_report") or {}
    pm = pr.get("pattern_match") or {}

    return {
        "case_id": c.get("case_id", ""),
        "alert_status": c.get("alert_status", "PENDING"),
        "verdict": c.get("verdict") or "—",
        "score": c.get("final_confidence_score") or 0,
        "pattern": pm.get("pattern_id") or sr.get("pattern_detected") or "—",
        "account_id": evt.get("account_id", "—"),
        "user_name": evt.get("metadata", {}).get("name") if isinstance(evt.get("metadata"), dict) else "—",
        "amount": evt.get("amount"),
        "currency": evt.get("currency", "USD"),
        "country": evt.get("country") or c.get("country", "—"),
        "event_type": evt.get("event_type", "—"),
        "ip_address": evt.get("ip_address", "—"),
        "device_id": evt.get("device_id", "—"),
        "created_at": c.get("created_at", ""),
        "latency_ms": c.get("total_latency_ms", 0),
        "tenant_id": c.get("tenant_id", ""),
        "tenant_name": tenants_map.get(c.get("tenant_id", ""), ""),
        "decision": c.get("decision"),
        "audit_log": c.get("audit_log", []),
    }


def _get_tenants_map() -> dict[str, str]:
    """Build tenant_id → name map from stored cases."""
    # In production this would query the tenant store
    return {}


# ── Endpoints ──


@router.get("/queue")
async def alert_queue(
    tenant_id: str | None = Query(None),
    status: str = Query("PENDING", pattern=r"^(PENDING|REVIEWING|ALL)$"),
    sort_by: str = Query("score", pattern=r"^(score|created_at|amount)$"),
    min_score: float = Query(0.0, ge=0, le=1),
    pattern: str | None = Query(None),
    country: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """Get the prioritized alert queue for analysts.

    Returns alerts sorted by risk score (highest first).
    Only returns cases with verdict != DISCARD (those are auto-dismissed).
    """
    store = get_cases_store()
    alerts = []

    for c in store.values():
        v = c.get("verdict")
        # Only cases that need review (not auto-dismissed)
        if v in (None, "DISCARD", "DISMISSED"):
            continue

        sc = c.get("final_confidence_score") or 0
        if sc < min_score:
            continue

        a_status = c.get("alert_status", "PENDING")
        if status != "ALL" and a_status != status:
            continue

        if tenant_id and c.get("tenant_id") != tenant_id:
            continue

        pr = c.get("pattern_report") or {}
        pm = pr.get("pattern_match") or {}
        if pattern and pm.get("pattern_id") != pattern:
            continue

        ev = c.get("enriched_event", {})
        evt = ev.get("event", {}) if isinstance(ev, dict) else {}
        if country and evt.get("country") != country:
            continue

        alerts.append(_extract_alert(c, {}))

    # Sort
    reverse = True
    if sort_by == "score":
        alerts.sort(key=lambda a: a["score"], reverse=True)
    elif sort_by == "created_at":
        alerts.sort(key=lambda a: a["created_at"], reverse=True)
    elif sort_by == "amount":
        alerts.sort(key=lambda a: a["amount"] or 0, reverse=True)

    total = len(alerts)
    paginated = alerts[offset:offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "alerts": paginated,
    }


@router.get("/queue/stats")
async def queue_stats(tenant_id: str | None = Query(None)) -> dict:
    """Stats for the alert queue header."""
    store = get_cases_store()
    pending = 0
    reviewing = 0
    resolved_today = 0
    by_verdict = {"MONITOR": 0, "ESCALATE": 0, "BLOCK": 0}
    by_pattern = {}
    scores = []

    for c in store.values():
        v = c.get("verdict")
        if v in (None, "DISCARD", "DISMISSED"):
            continue
        if tenant_id and c.get("tenant_id") != tenant_id:
            continue

        s = c.get("alert_status", "PENDING")
        if s == "PENDING":
            pending += 1
        elif s == "REVIEWING":
            reviewing += 1
        elif s in ("APPROVED", "REJECTED", "ESCALATED"):
            resolved_today += 1

        if v in by_verdict:
            by_verdict[v] += 1

        pr = c.get("pattern_report") or {}
        pm = pr.get("pattern_match") or {}
        pid = pm.get("pattern_id", "UNKNOWN")
        by_pattern[pid] = by_pattern.get(pid, 0) + 1

        scores.append(c.get("final_confidence_score") or 0)

    return {
        "pending": pending,
        "reviewing": reviewing,
        "resolved_today": resolved_today,
        "total_active": pending + reviewing,
        "by_verdict": by_verdict,
        "by_pattern": by_pattern,
        "avg_score": round(sum(scores) / len(scores), 4) if scores else 0,
        "critical_count": sum(1 for s in scores if s >= 0.85),
    }


@router.get("/{case_id}")
async def get_alert_detail(case_id: str) -> dict:
    """Full alert detail for the Case View — everything an analyst needs to decide."""
    store = get_cases_store()
    c = store.get(case_id)
    if not c:
        raise HTTPException(404, f"Case {case_id} not found")

    alert = _extract_alert(c, {})

    # Enrich with all agent reports for the case view
    alert["sentinel"] = c.get("sentinel_report")
    alert["osint"] = c.get("osint_report")
    alert["patterns"] = c.get("pattern_report")
    alert["historian"] = c.get("historian_report")
    alert["jurist"] = c.get("jurist_report")
    alert["executor"] = c.get("executor_report")
    alert["raw"] = c

    return alert


@router.post("/{case_id}/decide")
async def decide_alert(case_id: str, decision: Decision) -> dict:
    """Record an analyst's decision on an alert.

    Actions: APPROVE (confirm fraud), REJECT (false positive), ESCALATE (need more review).
    """
    store = get_cases_store()
    c = store.get(case_id)
    if not c:
        raise HTTPException(404, f"Case {case_id} not found")

    now = datetime.utcnow().isoformat()

    # Map action to alert_status
    status_map = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "ESCALATE": "ESCALATED"}
    new_status = status_map[decision.action]

    # Update case
    c["alert_status"] = new_status
    c["decision"] = {
        "action": decision.action,
        "analyst_id": decision.analyst_id,
        "analyst_name": decision.analyst_name,
        "reason": decision.reason,
        "notes": decision.notes,
        "decided_at": now,
    }

    # Append to audit log
    if "audit_log" not in c:
        c["audit_log"] = []
    c["audit_log"].append({
        "action": decision.action,
        "analyst_id": decision.analyst_id,
        "analyst_name": decision.analyst_name,
        "reason": decision.reason,
        "timestamp": now,
        "previous_status": "PENDING",
        "new_status": new_status,
    })

    store[case_id] = c

    return {
        "case_id": case_id,
        "new_status": new_status,
        "decision": c["decision"],
        "audit_log": c["audit_log"],
    }


@router.post("/{case_id}/assign")
async def assign_alert(case_id: str, body: dict) -> dict:
    """Assign an alert to an analyst for review."""
    store = get_cases_store()
    c = store.get(case_id)
    if not c:
        raise HTTPException(404, f"Case {case_id} not found")

    c["alert_status"] = "REVIEWING"
    c["assigned_to"] = body.get("analyst_id", "")
    c["assigned_name"] = body.get("analyst_name", "")

    if "audit_log" not in c:
        c["audit_log"] = []
    c["audit_log"].append({
        "action": "ASSIGN",
        "analyst_id": body.get("analyst_id", ""),
        "timestamp": datetime.utcnow().isoformat(),
        "previous_status": "PENDING",
        "new_status": "REVIEWING",
    })

    store[case_id] = c
    return {"case_id": case_id, "status": "REVIEWING", "assigned_to": c["assigned_to"]}
