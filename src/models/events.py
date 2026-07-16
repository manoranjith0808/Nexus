"""Banking event models for the ingestion layer."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    LOGIN = "login"
    TRANSFER = "transfer"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_OPENING = "account_opening"
    DEVICE_LINK = "device_link"
    BALANCE_INQUIRY = "balance_inquiry"


class BankingEvent(BaseModel):
    """Raw event from core banking system via Kafka."""

    event_id: str = Field(..., description="Unique event identifier")
    event_type: EventType
    timestamp: datetime
    account_id: str
    user_id: str
    country: str = Field(..., pattern=r"^(UY|AR)$", description="UY or AR")

    # Event-specific data
    amount: float | None = None
    currency: str | None = None
    destination_account: str | None = None
    destination_country: str | None = None
    device_id: str | None = None
    ip_address: str | None = None
    channel: str | None = Field(None, description="web, mobile, atm, branch")

    # Identity documents
    document_type: str | None = Field(None, description="cedula (UY) or DNI (AR)")
    document_number: str | None = None
    cbu_cvu: str | None = Field(None, description="CBU/CVU for AR accounts")

    metadata: dict[str, Any] = Field(default_factory=dict)


class GeoLocation(BaseModel):
    """IP geolocation data."""

    ip: str
    country: str
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_vpn: bool = False
    is_tor: bool = False
    is_proxy: bool = False
    isp: str | None = None
    asn: str | None = None


class DeviceReputation(BaseModel):
    """Device fingerprint and reputation."""

    device_id: str
    device_type: str | None = None
    os: str | None = None
    browser: str | None = None
    is_emulator: bool = False
    is_rooted: bool = False
    known_fraud: bool = False
    first_seen: datetime | None = None
    accounts_linked: int = 0


class RecentHistory(BaseModel):
    """Recent activity summary for an account."""

    events_last_1h: int = 0
    events_last_24h: int = 0
    events_last_7d: int = 0
    total_amount_24h: float = 0.0
    unique_destinations_24h: int = 0
    unique_ips_24h: int = 0
    unique_devices_24h: int = 0
    failed_logins_24h: int = 0
    password_changes_7d: int = 0


class EnrichedEvent(BaseModel):
    """Banking event enriched with metadata from the ingestion layer."""

    event: BankingEvent
    geo: GeoLocation | None = None
    device: DeviceReputation | None = None
    history: RecentHistory | None = None
    enrichment_timestamp: datetime = Field(default_factory=datetime.utcnow)
    enrichment_latency_ms: int = 0
