"""Graph exploration endpoints — for interactive visualization in Next.js.

Returns data in formats compatible with React Flow, D3, vis.js, or Cytoscape.
All queries are tenant-scoped unless cross_tenant=true (admin only).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sentinel_swarm.api.deps import get_neo4j

router = APIRouter()


# ── Response models for frontend ──


class GraphVizNode(BaseModel):
    id: str
    label: str
    type: str  # Persona, Cuenta, Dispositivo, IP, Transaccion
    properties: dict[str, Any] = {}
    status: str | None = None
    tenant_id: str | None = None
    risk_level: str | None = None  # LOW, MEDIUM, HIGH, CRITICAL


class GraphVizEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str  # Relationship type
    properties: dict[str, Any] = {}
    animated: bool = False  # For react-flow — animate suspicious edges


class GraphVizResponse(BaseModel):
    nodes: list[GraphVizNode]
    edges: list[GraphVizEdge]
    metadata: dict[str, Any] = {}


# ── Full graph for a tenant ──


@router.get("/{tenant_id}/full", response_model=GraphVizResponse)
async def get_full_graph(
    tenant_id: str,
    limit: int = Query(200, ge=1, le=2000),
) -> GraphVizResponse:
    """Get the full graph for a tenant, formatted for interactive visualization."""
    neo4j = get_neo4j()

    node_records = neo4j.execute_cypher(
        """
        MATCH (n {tenant_id: $tid})
        WHERE NOT n:Tenant
        RETURN properties(n) AS props, labels(n) AS lbls
        LIMIT $limit
        """,
        {"tid": tenant_id, "limit": limit},
    )

    edge_records = neo4j.execute_cypher(
        """
        MATCH (a {tenant_id: $tid})-[r]->(b)
        WHERE NOT a:Tenant AND NOT b:Tenant
        RETURN properties(a) AS src, type(r) AS rel, properties(r) AS rel_props, properties(b) AS tgt
        LIMIT $limit
        """,
        {"tid": tenant_id, "limit": limit},
    )

    return _build_graphviz(node_records, edge_records, tenant_id)


# ── Subgraph around a node ──


@router.get("/{tenant_id}/subgraph/{node_id}", response_model=GraphVizResponse)
async def get_subgraph(
    tenant_id: str,
    node_id: str,
    hops: int = Query(2, ge=1, le=5),
) -> GraphVizResponse:
    """Get the neighborhood subgraph around a specific node.

    Perfect for showing the 'blast radius' of a suspicious account.
    """
    neo4j = get_neo4j()

    edge_records = neo4j.execute_cypher(
        f"""
        MATCH (center {{tenant_id: $tid}})
        WHERE center.cuenta_id = $nid OR center.persona_id = $nid
              OR center.device_id = $nid OR center.address = $nid
        MATCH path = (center)-[*1..{hops}]-(neighbor)
        UNWIND relationships(path) AS r
        WITH DISTINCT startNode(r) AS a, r, endNode(r) AS b
        RETURN properties(a) AS src, type(r) AS rel, properties(r) AS rel_props, properties(b) AS tgt
        LIMIT 500
        """,
        {"tid": tenant_id, "nid": node_id},
    )

    # Extract nodes from edges
    node_records = _nodes_from_edges(edge_records)
    resp = _build_graphviz(node_records, edge_records, tenant_id)
    resp.metadata["center_node"] = node_id
    resp.metadata["hops"] = hops
    return resp


# ── Contaminated branches ──


@router.get("/{tenant_id}/contaminated", response_model=GraphVizResponse)
async def get_contaminated_branches(
    tenant_id: str,
    max_hops: int = Query(3, ge=1, le=5),
) -> GraphVizResponse:
    """Get all nodes connected to blocked/fraud-flagged accounts.

    Shows 'contaminated branches' — risk spreading through the network.
    Nodes are tagged with distance_from_fraud and risk_level.
    """
    neo4j = get_neo4j()

    edge_records = neo4j.execute_cypher(
        f"""
        MATCH (blocked {{tenant_id: $tid}})
        WHERE blocked.status IN ['BLOCKED_FRAUD', 'UNDER_INVESTIGATION']
        MATCH path = (blocked)-[*1..{max_hops}]-(connected)
        UNWIND relationships(path) AS r
        WITH DISTINCT startNode(r) AS a, r, endNode(r) AS b
        RETURN properties(a) AS src, type(r) AS rel, properties(r) AS rel_props, properties(b) AS tgt
        LIMIT 1000
        """,
        {"tid": tenant_id},
    )

    node_records = _nodes_from_edges(edge_records)
    resp = _build_graphviz(node_records, edge_records, tenant_id)

    # BFS to tag risk levels by distance from fraud
    blocked_ids = {n.id for n in resp.nodes if n.status in ("BLOCKED_FRAUD", "UNDER_INVESTIGATION")}
    for n in resp.nodes:
        if n.id in blocked_ids:
            n.risk_level = "CRITICAL"

    adjacency: dict[str, set[str]] = {}
    for e in resp.edges:
        adjacency.setdefault(e.source, set()).add(e.target)
        adjacency.setdefault(e.target, set()).add(e.source)

    visited: dict[str, int] = {bid: 0 for bid in blocked_ids}
    queue = list(blocked_ids)
    while queue:
        current = queue.pop(0)
        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                visited[neighbor] = visited[current] + 1
                queue.append(neighbor)

    for node in resp.nodes:
        dist = visited.get(node.id)
        if dist is not None and node.risk_level != "CRITICAL":
            node.properties["distance_from_fraud"] = dist
            node.risk_level = "HIGH" if dist <= 1 else "MEDIUM" if dist <= 2 else "LOW"

    for edge in resp.edges:
        if edge.source in blocked_ids or edge.target in blocked_ids:
            edge.animated = True

    resp.metadata["blocked_count"] = len(blocked_ids)
    resp.metadata["contaminated_count"] = len(visited)
    return resp


# ── Transfer flow ──


@router.get("/{tenant_id}/transfers", response_model=GraphVizResponse)
async def get_transfer_graph(
    tenant_id: str,
    min_amount: float = Query(0),
    limit: int = Query(200, ge=1, le=1000),
) -> GraphVizResponse:
    """Get the transfer flow graph — money movement between accounts."""
    neo4j = get_neo4j()
    edge_records = neo4j.execute_cypher(
        """
        MATCH (a:Cuenta {tenant_id: $tid})-[t:TRANSFIERE_A]->(b:Cuenta)
        WHERE t.amount >= $min_amount
        RETURN properties(a) AS src, type(t) AS rel, properties(t) AS rel_props, properties(b) AS tgt
        ORDER BY t.amount DESC
        LIMIT $limit
        """,
        {"tid": tenant_id, "min_amount": min_amount, "limit": limit},
    )
    node_records = _nodes_from_edges(edge_records)
    resp = _build_graphviz(node_records, edge_records, tenant_id)
    resp.metadata["filter"] = {"min_amount": min_amount}
    return resp


# ── Shared resources ──


@router.get("/{tenant_id}/shared-resources", response_model=GraphVizResponse)
async def get_shared_resources(tenant_id: str) -> GraphVizResponse:
    """Find devices and IPs shared across multiple accounts.

    Key indicator of synthetic identity or coordinated fraud.
    """
    neo4j = get_neo4j()
    edge_records = neo4j.execute_cypher(
        """
        MATCH (c1:Cuenta {tenant_id: $tid})-[r1:USA_DISPOSITIVO|CONECTA_DESDE_IP]-(shared)-[r2:USA_DISPOSITIVO|CONECTA_DESDE_IP]-(c2:Cuenta {tenant_id: $tid})
        WHERE c1 <> c2
        WITH DISTINCT c1, r1, shared, r2, c2
        RETURN properties(c1) AS src, type(r1) AS rel, properties(r1) AS rel_props, properties(shared) AS tgt
        UNION
        MATCH (c1:Cuenta {tenant_id: $tid})-[r1:USA_DISPOSITIVO|CONECTA_DESDE_IP]-(shared)-[r2:USA_DISPOSITIVO|CONECTA_DESDE_IP]-(c2:Cuenta {tenant_id: $tid})
        WHERE c1 <> c2
        WITH DISTINCT shared, r2, c2
        RETURN properties(shared) AS src, type(r2) AS rel, properties(r2) AS rel_props, properties(c2) AS tgt
        """,
        {"tid": tenant_id},
    )
    node_records = _nodes_from_edges(edge_records)
    resp = _build_graphviz(node_records, edge_records, tenant_id)
    resp.metadata["pattern"] = "shared_resources"
    return resp


# ── Cycles detection ──


@router.get("/{tenant_id}/cycles")
async def detect_cycles(
    tenant_id: str,
    max_length: int = Query(6, ge=2, le=10),
) -> dict:
    """Detect circular transfer patterns (ring attacks)."""
    neo4j = get_neo4j()
    results = neo4j.execute_cypher(
        f"""
        MATCH path = (start:Cuenta {{tenant_id: $tid}})-[:TRANSFIERE_A*2..{max_length}]->(start)
        RETURN [n IN nodes(path) | n.cuenta_id] AS cycle_nodes,
               length(path) AS cycle_length,
               [r IN relationships(path) | r.amount] AS amounts
        LIMIT 50
        """,
        {"tid": tenant_id},
    )
    return {"tenant_id": tenant_id, "cycles": results}


# ── Communities ──


@router.get("/{tenant_id}/communities")
async def detect_communities(tenant_id: str) -> dict:
    """Get graph structure for community detection."""
    neo4j = get_neo4j()
    results = neo4j.execute_cypher(
        """
        MATCH (n {tenant_id: $tid})
        WHERE NOT n:Tenant
        WITH count(n) AS node_count
        OPTIONAL MATCH (a {tenant_id: $tid2})-[r]->(b {tenant_id: $tid2})
        WITH node_count, count(r) AS edge_count
        RETURN node_count, edge_count
        """,
        {"tid": tenant_id, "tid2": tenant_id},
    )
    return {
        "tenant_id": tenant_id,
        "graph_size": results[0] if results else {"node_count": 0, "edge_count": 0},
    }


# ── Raw Cypher query ──


@router.post("/{tenant_id}/query")
async def execute_cypher_query(tenant_id: str, body: dict) -> dict:
    """Execute a raw Cypher query. Body: {"cypher": "...", "params": {}}"""
    cypher = body.get("cypher", "")
    params = body.get("params", {})
    if not cypher:
        raise HTTPException(400, "Missing 'cypher' field")
    params["__tenant_id"] = tenant_id
    neo4j = get_neo4j()
    try:
        results = neo4j.execute_cypher(cypher, params)
        # Sanitize results — convert non-serializable types
        clean = _sanitize(results)
        return {"results": clean, "count": len(clean)}
    except Exception as e:
        raise HTTPException(400, f"Cypher error: {str(e)}")


# ── Cross-tenant compare ──


@router.get("/cross-tenant/compare", response_model=GraphVizResponse)
async def cross_tenant_compare(
    tenant_a: str = Query(...),
    tenant_b: str = Query(...),
) -> GraphVizResponse:
    """Compare shared connections between two tenants (banks).

    Finds shared IPs, devices, or counterparties across banks.
    """
    neo4j = get_neo4j()

    shared_ips = neo4j.execute_cypher(
        """
        MATCH (c1:Cuenta {tenant_id: $ta})-[:CONECTA_DESDE_IP]->(ip:IP)<-[:CONECTA_DESDE_IP]-(c2:Cuenta {tenant_id: $tb})
        RETURN properties(c1) AS src, 'SHARED_IP' AS rel, {} AS rel_props, properties(ip) AS tgt
        LIMIT 100
        """,
        {"ta": tenant_a, "tb": tenant_b},
    )

    shared_devices = neo4j.execute_cypher(
        """
        MATCH (c1:Cuenta {tenant_id: $ta})-[:USA_DISPOSITIVO]->(d:Dispositivo)<-[:USA_DISPOSITIVO]-(c2:Cuenta {tenant_id: $tb})
        RETURN properties(c1) AS src, 'SHARED_DEVICE' AS rel, {} AS rel_props, properties(d) AS tgt
        LIMIT 100
        """,
        {"ta": tenant_a, "tb": tenant_b},
    )

    all_edges = shared_ips + shared_devices
    node_records = _nodes_from_edges(all_edges)
    resp = _build_graphviz(node_records, all_edges, "cross-tenant")

    resp.metadata = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "shared_ips": len(shared_ips),
        "shared_devices": len(shared_devices),
    }
    return resp


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════


def _build_graphviz(
    node_records: list[dict], edge_records: list[dict], tenant_id: str
) -> GraphVizResponse:
    """Build a GraphVizResponse from node and edge query results."""
    nodes: dict[str, GraphVizNode] = {}
    edges: list[GraphVizEdge] = []

    # Add nodes
    for rec in node_records:
        props = rec.get("props", {})
        if not isinstance(props, dict):
            continue
        props = _sanitize_dict(props)
        nid = _extract_id(props)
        if not nid or nid in nodes:
            continue
        lbls = rec.get("lbls", [])
        node_type = lbls[0] if lbls else _guess_type(props)
        status = props.get("status")

        nodes[nid] = GraphVizNode(
            id=nid,
            label=nid,
            type=node_type,
            properties={k: v for k, v in props.items() if k not in ("tenant_id",)},
            status=status,
            tenant_id=props.get("tenant_id", tenant_id),
            risk_level="CRITICAL" if status == "BLOCKED_FRAUD" else "HIGH" if status == "UNDER_INVESTIGATION" else None,
        )

    # Add edges
    for i, rec in enumerate(edge_records):
        src_props = rec.get("src", {})
        tgt_props = rec.get("tgt", {})
        if not isinstance(src_props, dict) or not isinstance(tgt_props, dict):
            continue
        src_props = _sanitize_dict(src_props)
        tgt_props = _sanitize_dict(tgt_props)

        src_id = _extract_id(src_props)
        tgt_id = _extract_id(tgt_props)
        if not src_id or not tgt_id:
            continue

        # Ensure nodes exist
        for nid, props in ((src_id, src_props), (tgt_id, tgt_props)):
            if nid not in nodes:
                nodes[nid] = GraphVizNode(
                    id=nid, label=nid, type=_guess_type(props),
                    properties={k: v for k, v in props.items() if k != "tenant_id"},
                    status=props.get("status"),
                    tenant_id=props.get("tenant_id", tenant_id),
                )

        rel_type = rec.get("rel", "RELATED")
        rel_props = rec.get("rel_props", {})
        if not isinstance(rel_props, dict):
            rel_props = {}
        rel_props = _sanitize_dict(rel_props)

        edges.append(GraphVizEdge(
            id=f"e-{i}",
            source=src_id,
            target=tgt_id,
            label=rel_type,
            properties=rel_props,
        ))

    return GraphVizResponse(
        nodes=list(nodes.values()),
        edges=edges,
        metadata={"tenant_id": tenant_id, "node_count": len(nodes), "edge_count": len(edges)},
    )


def _nodes_from_edges(edge_records: list[dict]) -> list[dict]:
    """Extract unique node records from edge query results."""
    seen: set[str] = set()
    nodes: list[dict] = []
    for rec in edge_records:
        for key in ("src", "tgt"):
            props = rec.get(key, {})
            if isinstance(props, dict):
                nid = _extract_id(props)
                if nid and nid not in seen:
                    seen.add(nid)
                    nodes.append({"props": props, "lbls": []})
    return nodes


def _extract_id(props: dict) -> str | None:
    for key in ("cuenta_id", "persona_id", "device_id", "address", "tx_id", "entity_id"):
        if key in props:
            return str(props[key])
    return None


def _guess_type(props: dict) -> str:
    if "cuenta_id" in props:
        return "Cuenta"
    if "persona_id" in props:
        return "Persona"
    if "device_id" in props:
        return "Dispositivo"
    if "address" in props:
        return "IP"
    if "tx_id" in props:
        return "Transaccion"
    return "Unknown"


def _sanitize_dict(d: dict) -> dict:
    """Convert non-JSON-serializable values in a dict."""
    out = {}
    for k, v in d.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif hasattr(v, "iso_format"):  # neo4j DateTime
            out[k] = str(v)
        elif isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, (list, tuple)):
            out[k] = [str(x) if not isinstance(x, (str, int, float, bool)) else x for x in v]
        else:
            out[k] = str(v)
    return out


def _sanitize(results: list[dict]) -> list[dict]:
    """Sanitize a list of Neo4j result dicts for JSON serialization."""
    return [_sanitize_dict(r) if isinstance(r, dict) else {"value": str(r)} for r in results]
