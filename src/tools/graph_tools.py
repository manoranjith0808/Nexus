"""LangChain tools wrapping Neo4j graph operations for agent use."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from sentinel_swarm.graph.neo4j_client import Neo4jClient

# Lazy singleton — initialized on first use
_client: Neo4jClient | None = None


def _get_client() -> Neo4jClient:
    global _client
    if _client is None:
        _client = Neo4jClient()
    return _client


@tool
def query_graph(cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
    """Execute a Cypher query on the Neo4j fraud graph. Use for custom graph traversals."""
    return _get_client().execute_cypher(cypher, params)


@tool
def run_gds_algorithm(algorithm: str, graph_name: str = "fraud_graph") -> list[dict]:
    """Run a GDS algorithm on the fraud graph.

    Args:
        algorithm: One of 'louvain', 'pagerank', 'betweenness', 'node_similarity'.
        graph_name: Name of the GDS graph projection.
    """
    client = _get_client()
    runners = {
        "louvain": client.run_louvain,
        "pagerank": client.run_pagerank,
        "betweenness": client.run_betweenness,
        "node_similarity": client.run_node_similarity,
    }
    runner = runners.get(algorithm)
    if not runner:
        return [{"error": f"Unknown algorithm: {algorithm}. Use: {list(runners.keys())}"}]
    return runner(graph_name)


@tool
def get_node_history(node_id: str, limit: int = 50) -> list[dict]:
    """Get recent transaction history for a node (account/persona)."""
    return _get_client().get_node_history(node_id, limit)


@tool
def check_blocked_proximity(node_id: str, max_hops: int = 2) -> list[dict]:
    """Check if a node is within N hops of a blocked/fraud-flagged account."""
    return _get_client().check_blocked_proximity(node_id, max_hops)


@tool
def detect_transfer_cycles(account_id: str, max_length: int = 6) -> list[dict]:
    """Detect circular transfer patterns (ring attacks) starting from an account."""
    return _get_client().detect_cycles(account_id, max_length)


@tool
def detect_shared_resources(account_id: str) -> list[dict]:
    """Find other accounts sharing devices or IPs with the given account."""
    return _get_client().detect_shared_resources(account_id)


@tool
def get_subgraph(center_node_id: str, hops: int = 2) -> dict:
    """Extract a subgraph around a node for analysis."""
    sg = _get_client().get_subgraph(center_node_id, hops)
    return sg.model_dump()
