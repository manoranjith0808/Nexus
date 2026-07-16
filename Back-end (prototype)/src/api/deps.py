"""Shared dependencies and state for the API layer.

Cases are persisted to data/cases_store.json so they survive restarts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import structlog

from sentinel_swarm.config import get_settings
from sentinel_swarm.utils.logging import setup_logging

logger = structlog.get_logger("api")

_state: dict[str, Any] = {}
CASES_FILE = Path(__file__).resolve().parents[3] / "data" / "cases_store.json"


def startup() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    # Neo4j — optional, don't crash if unavailable
    try:
        from sentinel_swarm.graph.neo4j_client import Neo4jClient
        from sentinel_swarm.graph.tenant_manager import TenantManager
        _state["neo4j"] = Neo4jClient()
        _state["tenant_mgr"] = TenantManager()
    except Exception as e:
        logger.warning("neo4j_unavailable", error=str(e))
        _state["neo4j"] = None
        _state["tenant_mgr"] = None

    # Orchestrator — optional
    try:
        from sentinel_swarm.orchestrator.graph import SentinelSwarmOrchestrator
        _state["orchestrator"] = SentinelSwarmOrchestrator()
    except Exception as e:
        logger.warning("orchestrator_unavailable", error=str(e))
        _state["orchestrator"] = None

    # Load persisted cases
    _state["cases"] = _load_cases()
    logger.info("api_started", cases_loaded=len(_state["cases"]))


def shutdown() -> None:
    _save_cases()
    if _state.get("neo4j"):
        _state["neo4j"].close()
    if _state.get("tenant_mgr"):
        _state["tenant_mgr"].close()
    logger.info("api_stopped")


def get_neo4j():
    n = _state.get("neo4j")
    if n is None:
        raise RuntimeError("Neo4j not available")
    return n


def get_tenant_mgr():
    t = _state.get("tenant_mgr")
    if t is None:
        raise RuntimeError("TenantManager not available")
    return t


def get_orchestrator():
    o = _state.get("orchestrator")
    if o is None:
        raise RuntimeError("Orchestrator not available")
    return o


def get_cases_store() -> dict[str, Any]:
    return _state["cases"]


def save_cases_to_disk() -> None:
    """Explicitly persist cases (called after bulk import)."""
    _save_cases()


# ── Persistence ──

def _load_cases() -> dict[str, Any]:
    if CASES_FILE.exists():
        try:
            with open(CASES_FILE) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            # If it's a list, convert to dict
            if isinstance(data, list):
                return {c["case_id"]: c for c in data if "case_id" in c}
        except Exception as e:
            logger.warning("cases_load_failed", error=str(e))
    return {}


def _save_cases() -> None:
    cases = _state.get("cases", {})
    if not cases:
        return
    try:
        CASES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CASES_FILE, "w") as f:
            json.dump(cases, f, separators=(",", ":"))
        logger.info("cases_saved", count=len(cases))
    except Exception as e:
        logger.error("cases_save_failed", error=str(e))
