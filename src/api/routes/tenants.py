"""Tenant (empresa/bank) management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from sentinel_swarm.api.deps import get_tenant_mgr
from sentinel_swarm.models.tenant import Tenant, TenantCreate, TenantUpdate

router = APIRouter()


@router.get("/", response_model=list[Tenant])
async def list_tenants():
    """List all registered banks/empresas."""
    return get_tenant_mgr().list_tenants()


@router.post("/", response_model=Tenant, status_code=201)
async def create_tenant(data: TenantCreate):
    """Register a new bank/empresa. Creates isolated data partition in the graph."""
    return get_tenant_mgr().create_tenant(data)


@router.get("/{tenant_id}", response_model=Tenant)
async def get_tenant(tenant_id: str):
    """Get a specific tenant by ID."""
    tenant = get_tenant_mgr().get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(404, f"Tenant {tenant_id} not found")
    return tenant


@router.patch("/{tenant_id}", response_model=Tenant)
async def update_tenant(tenant_id: str, data: TenantUpdate):
    """Update tenant configuration, status, or metadata."""
    tenant = get_tenant_mgr().update_tenant(tenant_id, data)
    if not tenant:
        raise HTTPException(404, f"Tenant {tenant_id} not found")
    return tenant


@router.delete("/{tenant_id}")
async def delete_tenant(tenant_id: str):
    """Delete a tenant and ALL its data. Irreversible."""
    ok = get_tenant_mgr().delete_tenant(tenant_id)
    if not ok:
        raise HTTPException(404, f"Tenant {tenant_id} not found")
    return {"deleted": True, "tenant_id": tenant_id}


@router.get("/{tenant_id}/stats")
async def tenant_stats(tenant_id: str):
    """Get graph statistics for a specific tenant."""
    tenant = get_tenant_mgr().get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(404, f"Tenant {tenant_id} not found")
    stats = get_tenant_mgr().get_tenant_stats(tenant_id)
    return {
        "tenant_id": tenant_id,
        "name": tenant.name,
        "total_cases": tenant.total_cases,
        "total_alerts": tenant.total_alerts,
        "total_blocked": tenant.total_blocked,
        "graph": stats,
    }


@router.get("/{tenant_id}/config")
async def tenant_config(tenant_id: str):
    """Get the current configuration for a tenant."""
    tenant = get_tenant_mgr().get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(404, f"Tenant {tenant_id} not found")
    return tenant.config
