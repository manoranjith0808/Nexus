"""Multi-tenant graph manager — isolates each bank's data in Neo4j while enabling cross-tenant training."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog
from neo4j import GraphDatabase

from sentinel_swarm.config import get_settings
from sentinel_swarm.models.tenant import Tenant, TenantConfig, TenantCreate, TenantStatus, TenantUpdate

logger = structlog.get_logger("graph.tenant_manager")


class TenantManager:
    """Manages tenant lifecycle and data isolation in Neo4j.

    Isolation strategy:
    - Every node gets a `tenant_id` property
    - Queries are scoped by tenant_id
    - Shared training data uses anonymized cross-tenant queries
    - Each tenant gets its own set of constraints/indexes on first setup
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    # ── Tenant CRUD ──

    def create_tenant(self, data: TenantCreate) -> Tenant:
        tenant_id = f"TNT-{uuid.uuid4().hex[:12]}"
        tenant = Tenant(
            tenant_id=tenant_id,
            name=data.name,
            country=data.country,
            regulatory_id=data.regulatory_id,
            compliance_officer=data.compliance_officer,
            compliance_email=data.compliance_email,
            config=data.config or TenantConfig(),
            metadata=data.metadata,
        )

        with self._driver.session() as session:
            session.run(
                """
                CREATE (t:Tenant {
                    tenant_id: $tid, name: $name, country: $country,
                    status: $status, created_at: datetime(),
                    regulatory_id: $reg_id, compliance_officer: $officer,
                    compliance_email: $email, config: $config,
                    total_cases: 0, total_alerts: 0, total_blocked: 0
                })
                """,
                tid=tenant_id,
                name=data.name,
                country=data.country.value,
                status=TenantStatus.ACTIVE.value,
                reg_id=data.regulatory_id,
                officer=data.compliance_officer,
                email=data.compliance_email,
                config=tenant.config.model_dump_json(),
            )

        self._setup_tenant_schema(tenant_id)
        logger.info("tenant_created", tenant_id=tenant_id, name=data.name)
        tenant.status = TenantStatus.ACTIVE
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (t:Tenant {tenant_id: $tid}) RETURN t",
                tid=tenant_id,
            )
            record = result.single()
            if not record:
                return None
            return self._node_to_tenant(record["t"])

    def list_tenants(self) -> list[Tenant]:
        with self._driver.session() as session:
            result = session.run("MATCH (t:Tenant) RETURN t ORDER BY t.created_at DESC")
            return [self._node_to_tenant(r["t"]) for r in result]

    def update_tenant(self, tenant_id: str, data: TenantUpdate) -> Tenant | None:
        sets: list[str] = ["t.updated_at = datetime()"]
        params: dict[str, Any] = {"tid": tenant_id}

        if data.name is not None:
            sets.append("t.name = $name")
            params["name"] = data.name
        if data.status is not None:
            sets.append("t.status = $status")
            params["status"] = data.status.value
        if data.compliance_officer is not None:
            sets.append("t.compliance_officer = $officer")
            params["officer"] = data.compliance_officer
        if data.compliance_email is not None:
            sets.append("t.compliance_email = $email")
            params["email"] = data.compliance_email
        if data.config is not None:
            sets.append("t.config = $config")
            params["config"] = data.config.model_dump_json()

        query = f"MATCH (t:Tenant {{tenant_id: $tid}}) SET {', '.join(sets)} RETURN t"
        with self._driver.session() as session:
            result = session.run(query, **params)
            record = result.single()
            if not record:
                return None
            return self._node_to_tenant(record["t"])

    def delete_tenant(self, tenant_id: str) -> bool:
        with self._driver.session() as session:
            # Delete all tenant data first
            session.run(
                "MATCH (n {tenant_id: $tid}) DETACH DELETE n",
                tid=tenant_id,
            )
            result = session.run(
                "MATCH (t:Tenant {tenant_id: $tid}) DETACH DELETE t RETURN count(t) AS deleted",
                tid=tenant_id,
            )
            record = result.single()
            return record and record["deleted"] > 0

    def increment_stats(self, tenant_id: str, field: str, amount: int = 1) -> None:
        valid = {"total_cases", "total_alerts", "total_blocked"}
        if field not in valid:
            return
        with self._driver.session() as session:
            session.run(
                f"MATCH (t:Tenant {{tenant_id: $tid}}) SET t.{field} = coalesce(t.{field}, 0) + $amt",
                tid=tenant_id, amt=amount,
            )

    # ── Tenant-scoped graph operations ──

    def get_tenant_stats(self, tenant_id: str) -> dict[str, Any]:
        with self._driver.session() as session:
            nodes = session.run(
                """
                MATCH (n {tenant_id: $tid})
                WHERE NOT n:Tenant
                RETURN labels(n)[0] AS tipo, count(n) AS cantidad
                ORDER BY cantidad DESC
                """,
                tid=tenant_id,
            )
            rels = session.run(
                """
                MATCH (a {tenant_id: $tid})-[r]->(b {tenant_id: $tid})
                RETURN type(r) AS tipo, count(r) AS cantidad
                ORDER BY cantidad DESC
                """,
                tid=tenant_id,
            )
            return {
                "nodes": [r.data() for r in nodes],
                "relations": [r.data() for r in rels],
            }

    # ── Private helpers ──

    def _setup_tenant_schema(self, tenant_id: str) -> None:
        """Ensure indexes exist for tenant-scoped queries."""
        # Composite indexes are created once globally, not per-tenant
        pass

    @staticmethod
    def _node_to_tenant(node) -> Tenant:
        import json
        props = dict(node)
        config_raw = props.pop("config", "{}")
        try:
            config = TenantConfig.model_validate_json(config_raw)
        except Exception:
            config = TenantConfig()

        return Tenant(
            tenant_id=props.get("tenant_id", ""),
            name=props.get("name", ""),
            country=props.get("country", "UY"),
            status=props.get("status", "ACTIVE"),
            config=config,
            regulatory_id=props.get("regulatory_id"),
            compliance_officer=props.get("compliance_officer"),
            compliance_email=props.get("compliance_email"),
            total_cases=props.get("total_cases", 0),
            total_alerts=props.get("total_alerts", 0),
            total_blocked=props.get("total_blocked", 0),
        )
