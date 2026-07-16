"""Health and system status endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from sentinel_swarm.api.deps import get_cases_store

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    neo4j_ok = False
    try:
        from sentinel_swarm.api.deps import get_neo4j
        neo4j_ok = get_neo4j().verify_connectivity()
    except Exception:
        pass

    tenant_count = 0
    try:
        from sentinel_swarm.api.deps import get_tenant_mgr
        tenants = get_tenant_mgr().list_tenants()
        tenant_count = len(tenants)
    except Exception:
        pass

    cases = get_cases_store()

    return {
        "status": "ok" if neo4j_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "neo4j": "connected" if neo4j_ok else "disconnected",
            "api": "running",
        },
        "stats": {
            "tenants": tenant_count,
            "cases_in_memory": len(cases),
        },
    }
