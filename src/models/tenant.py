"""Multi-tenant models — each empresa/bank is a tenant with isolated data."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TenantStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ONBOARDING = "ONBOARDING"


class TenantCountry(StrEnum):
    UY = "UY"
    AR = "AR"


class TenantConfig(BaseModel):
    """Per-tenant configurable thresholds and weights."""

    threshold_sentinel: float = 0.30
    threshold_block: float = 0.85
    threshold_escalate: float = 0.65
    threshold_monitor: float = 0.40
    monitoring_hours: int = 72
    ros_auto_submit: bool = True
    weight_sentinel: float = 0.25
    weight_osint: float = 0.20
    weight_patterns: float = 0.20
    weight_historian: float = 0.15
    weight_jurist: float = 0.20


class Tenant(BaseModel):
    """A bank/empresa registered in the system."""

    tenant_id: str
    name: str
    country: TenantCountry
    status: TenantStatus = TenantStatus.ONBOARDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    config: TenantConfig = Field(default_factory=TenantConfig)

    # Regulatory info
    regulatory_id: str | None = None  # BCU code for UY, BCRA code for AR
    compliance_officer: str | None = None
    compliance_email: str | None = None

    # Stats
    total_cases: int = 0
    total_alerts: int = 0
    total_blocked: int = 0

    metadata: dict[str, Any] = Field(default_factory=dict)


class TenantCreate(BaseModel):
    """Request body to create a new tenant."""

    name: str
    country: TenantCountry
    regulatory_id: str | None = None
    compliance_officer: str | None = None
    compliance_email: str | None = None
    config: TenantConfig | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TenantUpdate(BaseModel):
    """Request body to update a tenant."""

    name: str | None = None
    status: TenantStatus | None = None
    compliance_officer: str | None = None
    compliance_email: str | None = None
    config: TenantConfig | None = None
    metadata: dict[str, Any] | None = None
