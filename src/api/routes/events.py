"""Event processing endpoints — send banking events through the pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sentinel_swarm.api.deps import get_cases_store, get_neo4j, get_orchestrator, get_tenant_mgr
from sentinel_swarm.models.events import (
    BankingEvent,
    DeviceReputation,
    EnrichedEvent,
    EventType,
    GeoLocation,
    RecentHistory,
)

router = APIRouter()


class ProcessEventRequest(BaseModel):
    """Request to process a banking event through the 6-agent pipeline."""

    tenant_id: str
    account_id: str
    user_id: str
    event_type: str = "transfer"
    amount: float | None = None
    currency: str = "USD"
    destination_account: str | None = None
    destination_country: str | None = None
    ip_address: str | None = None
    device_id: str | None = None
    channel: str | None = None
    document_type: str | None = None
    document_number: str | None = None
    cbu_cvu: str | None = None

    # Enrichment overrides (for testing — in production these come from the enrichment pipeline)
    is_vpn: bool = False
    is_tor: bool = False
    email: str | None = None
    phone: str | None = None
    name: str | None = None

    # History overrides
    events_last_1h: int = 0
    events_last_24h: int = 0
    total_amount_24h: float = 0.0
    password_changes_7d: int = 0


class BulkProcessRequest(BaseModel):
    """Process multiple events at once."""

    events: list[ProcessEventRequest]


@router.post("/process")
async def process_event(req: ProcessEventRequest) -> dict:
    """Process a single banking event through the full 6-agent pipeline.

    The event is scoped to the specified tenant_id. Each tenant's data
    is isolated in the graph, but the AI models learn from anonymized
    cross-tenant patterns.
    """
    # Validate tenant
    tenant = get_tenant_mgr().get_tenant(req.tenant_id)
    if not tenant:
        raise HTTPException(404, f"Tenant {req.tenant_id} not found")

    # Build event
    event = BankingEvent(
        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
        event_type=EventType(req.event_type),
        timestamp=datetime.utcnow(),
        account_id=req.account_id,
        user_id=req.user_id,
        country=tenant.country.value,
        amount=req.amount,
        currency=req.currency,
        destination_account=req.destination_account,
        destination_country=req.destination_country,
        device_id=req.device_id,
        ip_address=req.ip_address,
        channel=req.channel,
        document_type=req.document_type,
        document_number=req.document_number,
        cbu_cvu=req.cbu_cvu,
        metadata={
            "email": req.email,
            "phone": req.phone,
            "name": req.name,
            "tenant_id": req.tenant_id,
        },
    )

    enriched = EnrichedEvent(
        event=event,
        geo=GeoLocation(
            ip=req.ip_address or "0.0.0.0",
            country="Unknown",
            is_vpn=req.is_vpn,
            is_tor=req.is_tor,
        ) if req.ip_address else None,
        device=DeviceReputation(
            device_id=req.device_id or "unknown",
            known_fraud=False,
            accounts_linked=1,
        ) if req.device_id else None,
        history=RecentHistory(
            events_last_1h=req.events_last_1h,
            events_last_24h=req.events_last_24h,
            total_amount_24h=req.total_amount_24h,
            password_changes_7d=req.password_changes_7d,
        ),
    )

    # Ingest into tenant-scoped graph
    try:
        neo4j = get_neo4j()
        neo4j.ingest_event(enriched)
        # Tag all created nodes with tenant_id
        _tag_tenant(neo4j, req.tenant_id, req.account_id, req.user_id, req.device_id, req.ip_address)
    except Exception:
        pass  # Graph ingestion is non-blocking

    # Process through pipeline
    orchestrator = get_orchestrator()
    result = await orchestrator.process_event(enriched)

    # Store case
    case_data = result.model_dump(mode="json")
    case_data["tenant_id"] = req.tenant_id
    get_cases_store()[result.case_id] = case_data

    # Update tenant stats
    mgr = get_tenant_mgr()
    mgr.increment_stats(req.tenant_id, "total_cases")
    if result.verdict and result.verdict.value in ("ESCALATE", "BLOCK", "MONITOR"):
        mgr.increment_stats(req.tenant_id, "total_alerts")
    if result.verdict and result.verdict.value == "BLOCK":
        mgr.increment_stats(req.tenant_id, "total_blocked")

    return case_data


@router.post("/process/bulk")
async def process_bulk(req: BulkProcessRequest) -> dict:
    """Process multiple events. Returns summary of results."""
    results = []
    for event_req in req.events:
        try:
            result = await process_event(event_req)
            results.append({"case_id": result["case_id"], "verdict": result.get("verdict"), "status": "ok"})
        except Exception as e:
            results.append({"error": str(e), "status": "failed"})

    return {
        "total": len(req.events),
        "processed": sum(1 for r in results if r["status"] == "ok"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    }


def _tag_tenant(neo4j: Any, tenant_id: str, account_id: str, user_id: str, device_id: str | None, ip: str | None) -> None:
    """Tag all nodes from this event with the tenant_id for isolation."""
    queries = [
        ("MATCH (c:Cuenta {cuenta_id: $id}) SET c.tenant_id = $tid", {"id": account_id, "tid": tenant_id}),
        ("MATCH (p:Persona {persona_id: $id}) SET p.tenant_id = $tid", {"id": user_id, "tid": tenant_id}),
    ]
    if device_id:
        queries.append(("MATCH (d:Dispositivo {device_id: $id}) SET d.tenant_id = $tid", {"id": device_id, "tid": tenant_id}))
    if ip:
        queries.append(("MATCH (i:IP {address: $id}) SET i.tenant_id = $tid", {"id": ip, "tid": tenant_id}))

    for q, p in queries:
        try:
            neo4j.execute_cypher(q, p)
        except Exception:
            pass
