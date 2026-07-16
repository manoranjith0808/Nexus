"""Event enrichment pipeline — adds geolocation, device reputation, and history."""

from __future__ import annotations

from datetime import datetime

import httpx
import structlog

from sentinel_swarm.config import get_settings
from sentinel_swarm.models.events import (
    BankingEvent,
    DeviceReputation,
    EnrichedEvent,
    GeoLocation,
    RecentHistory,
)

logger = structlog.get_logger("ingestion.enrichment")


class EnrichmentPipeline:
    """Enriches raw banking events with contextual metadata."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._http = httpx.Client(timeout=3.0)

    def enrich(self, event: BankingEvent) -> EnrichedEvent:
        """Run all enrichment steps. Non-critical failures are logged but don't block."""
        geo = self._enrich_geo(event.ip_address) if event.ip_address else None
        device = self._enrich_device(event.device_id) if event.device_id else None
        history = self._enrich_history(event.account_id)

        return EnrichedEvent(
            event=event,
            geo=geo,
            device=device,
            history=history,
            enrichment_timestamp=datetime.utcnow(),
        )

    def _enrich_geo(self, ip: str) -> GeoLocation | None:
        """Resolve IP geolocation and VPN/TOR detection."""
        try:
            # MaxMind GeoIP2 lookup (production would use local DB)
            # Fallback: ip-api.com for development
            resp = self._http.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country,city,lat,lon,isp,as,proxy,hosting"},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            if data.get("status") != "success":
                return None

            return GeoLocation(
                ip=ip,
                country=data.get("country", "Unknown"),
                city=data.get("city"),
                latitude=data.get("lat"),
                longitude=data.get("lon"),
                isp=data.get("isp"),
                asn=data.get("as"),
                is_vpn=data.get("proxy", False),
                is_proxy=data.get("hosting", False),
            )
        except Exception as e:
            logger.warning("geo_enrichment_failed", ip=ip, error=str(e))
            return None

    def _enrich_device(self, device_id: str) -> DeviceReputation | None:
        """Look up device reputation from internal registry."""
        try:
            # In production: query internal device fingerprint DB or Redis cache
            # For now, return a baseline reputation
            return DeviceReputation(
                device_id=device_id,
                known_fraud=False,
                accounts_linked=1,
            )
        except Exception as e:
            logger.warning("device_enrichment_failed", device_id=device_id, error=str(e))
            return None

    def _enrich_history(self, account_id: str) -> RecentHistory | None:
        """Fetch recent activity summary from Redis/cache."""
        try:
            # In production: aggregate from Redis sorted sets or pre-computed counters
            return RecentHistory()
        except Exception as e:
            logger.warning("history_enrichment_failed", account_id=account_id, error=str(e))
            return None
