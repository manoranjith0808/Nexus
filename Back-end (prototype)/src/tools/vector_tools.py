"""LangChain tools for vector search (RAG) used by the Historian agent."""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger("tools.vector")

# In production: ChromaDB or similar vector store client
_MOCK_CASES: list[dict[str, Any]] = [
    {
        "case_id": "HIST-001",
        "pattern": "SMURFING",
        "result": "FRAUD_CONFIRMED",
        "action": "Account blocked, ROS submitted to UIAF",
        "losses_usd": 45_000,
        "resolution": "Judicial proceeding initiated",
        "modus_operandi": "Multiple small deposits across 8 mule accounts funneled to offshore entity",
        "similarity": 0.0,
    },
    {
        "case_id": "HIST-002",
        "pattern": "ACCOUNT_TAKEOVER",
        "result": "FRAUD_CONFIRMED",
        "action": "Transaction reversed, account frozen",
        "losses_usd": 12_000,
        "resolution": "Funds recovered, SIM swap ring dismantled",
        "modus_operandi": "SIM swap followed by password reset and wire transfer within 10 minutes",
        "similarity": 0.0,
    },
    {
        "case_id": "HIST-003",
        "pattern": "IDENTIDAD_SINTETICA",
        "result": "FRAUD_CONFIRMED",
        "action": "Network of 15 accounts blocked, ROS to UIF",
        "losses_usd": 230_000,
        "resolution": "Criminal investigation ongoing",
        "modus_operandi": "Synthetic identities using real stolen data, shared devices across accounts",
        "similarity": 0.0,
    },
    {
        "case_id": "HIST-004",
        "pattern": "LAYERING",
        "result": "FRAUD_CONFIRMED",
        "action": "Cascade block, international ROS",
        "losses_usd": 890_000,
        "resolution": "GAFILAT cooperation, assets frozen in 3 jurisdictions",
        "modus_operandi": "6-layer cascade through shell companies in 4 countries",
        "similarity": 0.0,
    },
    {
        "case_id": "HIST-005",
        "pattern": "SMURFING",
        "result": "FALSE_POSITIVE",
        "action": "Monitoring period, cleared after 72h",
        "losses_usd": 0,
        "resolution": "Client verified — legitimate business payments",
        "modus_operandi": "Legitimate payroll distribution flagged due to pattern similarity",
        "similarity": 0.0,
    },
    {
        "case_id": "HIST-006",
        "pattern": "ROUND_TRIPPING",
        "result": "FRAUD_CONFIRMED",
        "action": "Both accounts blocked, ROS to both UIAF and UIF",
        "losses_usd": 67_000,
        "resolution": "Tax evasion scheme identified",
        "modus_operandi": "Circular transfers between UY and AR accounts to simulate business activity",
        "similarity": 0.0,
    },
]


@tool
def vector_search(
    query_text: str,
    pattern_type: str | None = None,
    k: int = 10,
    min_similarity: float = 0.70,
) -> list[dict]:
    """Search the vector database of historical fraud cases.

    Args:
        query_text: Description of the current case for similarity matching.
        pattern_type: Optional filter by pattern type (SMURFING, LAYERING, etc.).
        k: Number of results to return (max 10).
        min_similarity: Minimum cosine similarity threshold.
    """
    # In production: embed query_text, search ChromaDB
    # For now: return mock cases filtered by pattern if specified
    results = _MOCK_CASES.copy()

    if pattern_type:
        results = [c for c in results if c["pattern"] == pattern_type]

    # Simulate similarity scores
    for i, case in enumerate(results):
        case["similarity"] = round(max(0.75 - (i * 0.05), min_similarity), 2)

    results = [c for c in results if c["similarity"] >= min_similarity]
    return results[:k]


@tool
def get_case_detail(case_id: str) -> dict:
    """Get full details of a historical fraud case by ID."""
    for case in _MOCK_CASES:
        if case["case_id"] == case_id:
            return case
    return {"error": f"Case {case_id} not found"}


@tool
def get_fraud_stats(pattern_type: str | None = None) -> dict:
    """Get aggregate fraud statistics from historical cases.

    Returns: total_cases, fraud_rate, avg_losses, common_patterns.
    """
    cases = _MOCK_CASES
    if pattern_type:
        cases = [c for c in cases if c["pattern"] == pattern_type]

    total = len(cases)
    confirmed = sum(1 for c in cases if c["result"] == "FRAUD_CONFIRMED")
    total_losses = sum(c["losses_usd"] for c in cases)

    return {
        "total_cases": total,
        "fraud_confirmed": confirmed,
        "false_positives": total - confirmed,
        "fraud_rate": round(confirmed / total, 2) if total > 0 else 0.0,
        "total_losses_usd": total_losses,
        "avg_losses_usd": round(total_losses / confirmed, 2) if confirmed > 0 else 0.0,
    }


@tool
def embed_case(case_description: str, case_id: str, metadata: dict | None = None) -> dict:
    """Embed and store a new case in the vector database for future RAG retrieval."""
    # In production: compute embedding, store in ChromaDB
    logger.info("case_embedded", case_id=case_id)
    return {
        "case_id": case_id,
        "status": "STORED",
        "vector_dimensions": 1024,
    }
