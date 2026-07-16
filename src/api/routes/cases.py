"""Case management endpoints — query and manage processed cases."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from sentinel_swarm.api.deps import get_cases_store, save_cases_to_disk

router = APIRouter()


@router.get("/")
async def list_cases(
    tenant_id: str | None = Query(None, description="Filter by tenant"),
    verdict: str | None = Query(None, description="Filter by verdict: DISCARD, MONITOR, ESCALATE, BLOCK"),
    min_score: float | None = Query(None, ge=0, le=1, description="Minimum confidence score"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """List processed cases with filters."""
    all_cases = list(get_cases_store().values())

    # Apply filters
    if tenant_id:
        all_cases = [c for c in all_cases if c.get("tenant_id") == tenant_id]
    if verdict:
        all_cases = [c for c in all_cases if c.get("verdict") == verdict]
    if min_score is not None:
        all_cases = [c for c in all_cases if (c.get("final_confidence_score") or 0) >= min_score]

    total = len(all_cases)
    paginated = all_cases[offset : offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "cases": paginated,
    }


@router.get("/{case_id}")
async def get_case(case_id: str) -> dict:
    """Get full details of a specific case including all agent reports."""
    cases = get_cases_store()
    if case_id not in cases:
        raise HTTPException(404, f"Case {case_id} not found")
    return cases[case_id]


@router.get("/{case_id}/timeline")
async def case_timeline(case_id: str) -> dict:
    """Get the execution timeline of a case — when each agent ran and what it found."""
    cases = get_cases_store()
    if case_id not in cases:
        raise HTTPException(404, f"Case {case_id} not found")

    c = cases[case_id]
    timeline = []

    agents = [
        ("sentinel", "El Centinela", c.get("sentinel_report")),
        ("osint", "Investigador OSINT", c.get("osint_report")),
        ("patterns", "Arquitecto de Patrones", c.get("pattern_report")),
        ("historian", "Historiador Forense", c.get("historian_report")),
        ("jurist", "Jurista Compliance", c.get("jurist_report")),
        ("executor", "El Ejecutor", c.get("executor_report")),
    ]

    for agent_id, name, report in agents:
        if report:
            timeline.append({
                "agent_id": agent_id,
                "agent_name": name,
                "timestamp": report.get("timestamp"),
                "latency_ms": report.get("latency_ms", 0),
                "risk_score": report.get("risk_score"),
                "confidence": report.get("confidence"),
                "findings_count": len(report.get("findings", [])),
                "recommendation": report.get("recommendation", ""),
            })

    return {
        "case_id": case_id,
        "verdict": c.get("verdict"),
        "total_latency_ms": c.get("total_latency_ms"),
        "timeline": timeline,
    }


@router.get("/{case_id}/agents/{agent_id}")
async def case_agent_detail(case_id: str, agent_id: str) -> dict:
    """Get the full report from a specific agent for a case."""
    cases = get_cases_store()
    if case_id not in cases:
        raise HTTPException(404, f"Case {case_id} not found")

    agent_map = {
        "sentinel": "sentinel_report",
        "osint": "osint_report",
        "patterns": "pattern_report",
        "historian": "historian_report",
        "jurist": "jurist_report",
        "executor": "executor_report",
    }

    key = agent_map.get(agent_id)
    if not key:
        raise HTTPException(400, f"Invalid agent_id: {agent_id}. Valid: {list(agent_map.keys())}")

    report = cases[case_id].get(key)
    if not report:
        raise HTTPException(404, f"No report from {agent_id} for case {case_id}")

    return report


@router.post("/import")
async def import_cases(body: dict) -> dict:
    """Bulk import pre-computed cases (for seeding/migration)."""
    cases_list = body.get("cases", [])
    store = get_cases_store()
    imported = 0
    for c in cases_list:
        cid = c.get("case_id")
        if cid:
            store[cid] = c
            imported += 1
    # Persist to disk after bulk import
    if imported > 0:
        save_cases_to_disk()
    return {"imported": imported, "total_in_store": len(store)}


@router.get("/stats/summary")
async def cases_summary(tenant_id: str | None = Query(None)) -> dict:
    """Aggregate stats across all cases (optionally filtered by tenant)."""
    all_cases = list(get_cases_store().values())
    if tenant_id:
        all_cases = [c for c in all_cases if c.get("tenant_id") == tenant_id]

    total = len(all_cases)
    if total == 0:
        return {"total": 0, "verdicts": {}, "avg_score": 0, "avg_latency_ms": 0}

    verdicts: dict[str, int] = {}
    scores = []
    latencies = []

    for c in all_cases:
        v = c.get("verdict") or "DISMISSED"
        verdicts[v] = verdicts.get(v, 0) + 1
        if c.get("final_confidence_score") is not None:
            scores.append(c["final_confidence_score"])
        latencies.append(c.get("total_latency_ms", 0))

    return {
        "total": total,
        "verdicts": verdicts,
        "avg_score": round(sum(scores) / len(scores), 4) if scores else 0,
        "avg_latency_ms": round(sum(latencies) / len(latencies)),
        "max_latency_ms": max(latencies),
        "min_latency_ms": min(latencies),
    }
