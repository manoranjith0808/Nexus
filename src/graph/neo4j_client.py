"""Neo4j client with GDS algorithm support for the graph layer."""

from __future__ import annotations

from typing import Any

import structlog
from neo4j import GraphDatabase, ManagedTransaction
from tenacity import retry, stop_after_attempt, wait_exponential

from sentinel_swarm.config import get_settings
from sentinel_swarm.models.events import BankingEvent, EnrichedEvent
from sentinel_swarm.models.graph import GraphNode, GraphRelation, NodeType, RelationType, SubGraph

logger = structlog.get_logger("graph.neo4j")


class Neo4jClient:
    """Neo4j driver wrapper with domain-specific graph operations and GDS algorithms."""

    def __init__(self) -> None:
        settings = get_settings()
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        logger.info("neo4j_connected", uri=settings.neo4j_uri)

    def close(self) -> None:
        self._driver.close()

    def verify_connectivity(self) -> bool:
        try:
            self._driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error("neo4j_connectivity_failed", error=str(e))
            return False

    # ── Event Ingestion into Graph ──

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=2))
    def ingest_event(self, enriched: EnrichedEvent) -> None:
        """Ingest an enriched banking event into the graph."""
        event = enriched.event
        with self._driver.session() as session:
            # Ensure Persona node
            session.execute_write(
                self._merge_persona, event.user_id, event.document_type, event.document_number
            )
            # Ensure Cuenta node
            session.execute_write(
                self._merge_cuenta, event.account_id, event.country, event.cbu_cvu
            )
            # Link Persona → Cuenta
            session.execute_write(
                self._merge_relation,
                "Persona", "persona_id", event.user_id,
                "Cuenta", "cuenta_id", event.account_id,
                "ES_TITULAR_DE",
            )
            # Device node + relation
            if event.device_id:
                is_fraud = enriched.device.known_fraud if enriched.device else False
                session.execute_write(self._merge_dispositivo, event.device_id, is_fraud)
                session.execute_write(
                    self._merge_relation,
                    "Cuenta", "cuenta_id", event.account_id,
                    "Dispositivo", "device_id", event.device_id,
                    "USA_DISPOSITIVO",
                )
            # IP node + relation
            if event.ip_address:
                geo = enriched.geo
                session.execute_write(
                    self._merge_ip,
                    event.ip_address,
                    geo.is_vpn if geo else False,
                    geo.is_tor if geo else False,
                    geo.country if geo else "Unknown",
                )
                session.execute_write(
                    self._merge_relation,
                    "Cuenta", "cuenta_id", event.account_id,
                    "IP", "address", event.ip_address,
                    "CONECTA_DESDE_IP",
                )
            # Transfer → Transaccion node + relations
            if event.event_type == "transfer" and event.destination_account:
                session.execute_write(
                    self._create_transfer,
                    event.event_id, event.account_id, event.destination_account,
                    event.amount or 0.0, event.currency or "USD", event.timestamp.isoformat(),
                )

    @staticmethod
    def _merge_persona(tx: ManagedTransaction, user_id: str, doc_type: str | None, doc_num: str | None) -> None:
        tx.run(
            """
            MERGE (p:Persona {persona_id: $user_id})
            ON CREATE SET p.document_type = $doc_type, p.document_number = $doc_num,
                          p.created_at = datetime()
            """,
            user_id=user_id, doc_type=doc_type, doc_num=doc_num,
        )

    @staticmethod
    def _merge_cuenta(tx: ManagedTransaction, account_id: str, country: str, cbu_cvu: str | None) -> None:
        tx.run(
            """
            MERGE (c:Cuenta {cuenta_id: $account_id})
            ON CREATE SET c.country = $country, c.cbu_cvu = $cbu_cvu,
                          c.created_at = datetime(), c.status = 'ACTIVE'
            """,
            account_id=account_id, country=country, cbu_cvu=cbu_cvu,
        )

    @staticmethod
    def _merge_dispositivo(tx: ManagedTransaction, device_id: str, known_fraud: bool) -> None:
        tx.run(
            """
            MERGE (d:Dispositivo {device_id: $device_id})
            ON CREATE SET d.known_fraud = $known_fraud, d.first_seen = datetime()
            SET d.last_seen = datetime()
            """,
            device_id=device_id, known_fraud=known_fraud,
        )

    @staticmethod
    def _merge_ip(tx: ManagedTransaction, address: str, is_vpn: bool, is_tor: bool, country: str) -> None:
        risk = "HIGH" if (is_vpn or is_tor) else "LOW"
        tx.run(
            """
            MERGE (i:IP {address: $address})
            ON CREATE SET i.is_vpn = $is_vpn, i.is_tor = $is_tor,
                          i.country = $country, i.risk_level = $risk
            SET i.last_seen = datetime()
            """,
            address=address, is_vpn=is_vpn, is_tor=is_tor, country=country, risk=risk,
        )

    @staticmethod
    def _merge_relation(
        tx: ManagedTransaction,
        src_label: str, src_key: str, src_val: str,
        tgt_label: str, tgt_key: str, tgt_val: str,
        rel_type: str,
    ) -> None:
        query = f"""
            MATCH (a:{src_label} {{{src_key}: $src_val}})
            MATCH (b:{tgt_label} {{{tgt_key}: $tgt_val}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r.last_seen = datetime()
        """
        tx.run(query, src_val=src_val, tgt_val=tgt_val)

    @staticmethod
    def _create_transfer(
        tx: ManagedTransaction,
        tx_id: str, src_account: str, dst_account: str,
        amount: float, currency: str, timestamp: str,
    ) -> None:
        tx.run(
            """
            MERGE (dst:Cuenta {cuenta_id: $dst_account})
            ON CREATE SET dst.created_at = datetime(), dst.status = 'ACTIVE'
            WITH dst
            MATCH (src:Cuenta {cuenta_id: $src_account})
            CREATE (t:Transaccion {
                tx_id: $tx_id, amount: $amount, currency: $currency,
                timestamp: datetime($timestamp), status: 'COMPLETED'
            })
            CREATE (src)-[:TRANSFIERE_A {amount: $amount, timestamp: datetime($timestamp)}]->(dst)
            CREATE (src)-[:ORIGINA]->(t)
            CREATE (t)-[:DESTINO]->(dst)
            """,
            tx_id=tx_id, src_account=src_account, dst_account=dst_account,
            amount=amount, currency=currency, timestamp=timestamp,
        )

    # ── Query Operations (used by agents) ──

    def execute_cypher(self, query: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Execute arbitrary Cypher query and return results as dicts."""
        with self._driver.session() as session:
            result = session.run(query, parameters=params or {})
            return [record.data() for record in result]

    def get_subgraph(self, center_node_id: str, hops: int = 2) -> SubGraph:
        """Extract a subgraph around a node up to N hops."""
        query = """
            MATCH path = (center)-[*1..$hops]-(neighbor)
            WHERE center.cuenta_id = $node_id
               OR center.persona_id = $node_id
               OR center.device_id = $node_id
            RETURN path
            LIMIT 500
        """
        with self._driver.session() as session:
            result = session.run(query, node_id=center_node_id, hops=hops)
            nodes_map: dict[str, GraphNode] = {}
            relations: list[GraphRelation] = []

            for record in result:
                path = record["path"]
                for node in path.nodes:
                    nid = str(node.element_id)
                    if nid not in nodes_map:
                        labels = list(node.labels)
                        node_type = self._label_to_node_type(labels)
                        nodes_map[nid] = GraphNode(
                            node_id=nid,
                            node_type=node_type,
                            properties=dict(node),
                            labels=labels,
                        )
                for rel in path.relationships:
                    relations.append(GraphRelation(
                        source_id=str(rel.start_node.element_id),
                        target_id=str(rel.end_node.element_id),
                        relation_type=self._rel_to_type(rel.type),
                        properties=dict(rel),
                    ))

            return SubGraph(
                nodes=list(nodes_map.values()),
                relations=relations,
                center_node_id=center_node_id,
            )

    def get_node_history(self, node_id: str, limit: int = 50) -> list[dict]:
        """Get recent transaction history for a node."""
        query = """
            MATCH (c:Cuenta {cuenta_id: $node_id})-[:TRANSFIERE_A]->(dest)
            RETURN c.cuenta_id AS source, dest.cuenta_id AS destination,
                   c.status AS source_status
            ORDER BY dest.created_at DESC
            LIMIT $limit
        """
        return self.execute_cypher(query, {"node_id": node_id, "limit": limit})

    def check_blocked_proximity(self, node_id: str, max_hops: int = 2) -> list[dict]:
        """Check if a node is within N hops of a blocked account."""
        query = f"""
            MATCH (start:Cuenta {{cuenta_id: $node_id}})
            MATCH (blocked:Cuenta {{status: 'BLOCKED_FRAUD'}})
            WHERE start <> blocked
            MATCH path = shortestPath((start)-[*1..{max_hops}]-(blocked))
            RETURN blocked.cuenta_id AS blocked_account,
                   length(path) AS distance,
                   [n IN nodes(path) | coalesce(n.cuenta_id, n.persona_id, n.device_id)] AS path_nodes
            LIMIT 10
        """
        return self.execute_cypher(query, {"node_id": node_id})

    # ── GDS Algorithm Wrappers ──

    def run_louvain(self, graph_name: str = "fraud_graph") -> list[dict]:
        """Run Louvain community detection."""
        self._ensure_gds_projection(graph_name)
        return self.execute_cypher(f"""
            CALL gds.louvain.stream('{graph_name}')
            YIELD nodeId, communityId
            RETURN gds.util.asNode(nodeId).cuenta_id AS node, communityId
            ORDER BY communityId
        """)

    def run_pagerank(self, graph_name: str = "fraud_graph") -> list[dict]:
        """Run PageRank to find important nodes."""
        self._ensure_gds_projection(graph_name)
        return self.execute_cypher(f"""
            CALL gds.pageRank.stream('{graph_name}')
            YIELD nodeId, score
            RETURN gds.util.asNode(nodeId).cuenta_id AS node, score
            ORDER BY score DESC
            LIMIT 50
        """)

    def run_betweenness(self, graph_name: str = "fraud_graph") -> list[dict]:
        """Run betweenness centrality to find bridge nodes."""
        self._ensure_gds_projection(graph_name)
        return self.execute_cypher(f"""
            CALL gds.betweenness.stream('{graph_name}')
            YIELD nodeId, score
            RETURN gds.util.asNode(nodeId).cuenta_id AS node, score
            ORDER BY score DESC
            LIMIT 50
        """)

    def run_node_similarity(self, graph_name: str = "fraud_graph") -> list[dict]:
        """Run Jaccard node similarity."""
        self._ensure_gds_projection(graph_name)
        return self.execute_cypher(f"""
            CALL gds.nodeSimilarity.stream('{graph_name}')
            YIELD node1, node2, similarity
            RETURN gds.util.asNode(node1).cuenta_id AS node_a,
                   gds.util.asNode(node2).cuenta_id AS node_b,
                   similarity
            ORDER BY similarity DESC
            LIMIT 50
        """)

    def detect_cycles(self, account_id: str, max_length: int = 6) -> list[dict]:
        """Detect transfer cycles (ring attacks)."""
        query = f"""
            MATCH path = (start:Cuenta {{cuenta_id: $account_id}})-[:TRANSFIERE_A*2..{max_length}]->(start)
            RETURN [n IN nodes(path) | n.cuenta_id] AS cycle_nodes,
                   length(path) AS cycle_length
            LIMIT 20
        """
        return self.execute_cypher(query, {"account_id": account_id})

    def detect_shared_resources(self, account_id: str) -> list[dict]:
        """Find accounts sharing devices or IPs with the given account."""
        query = """
            MATCH (c1:Cuenta {cuenta_id: $account_id})-[:USA_DISPOSITIVO|CONECTA_DESDE_IP]-(shared)-[:USA_DISPOSITIVO|CONECTA_DESDE_IP]-(c2:Cuenta)
            WHERE c1 <> c2
            RETURN c2.cuenta_id AS shared_account,
                   labels(shared) AS shared_resource_type,
                   coalesce(shared.device_id, shared.address) AS shared_resource_id
        """
        return self.execute_cypher(query, {"account_id": account_id})

    def update_node_status(self, account_id: str, status: str, labels: list[str] | None = None) -> None:
        """Update a node's status and optionally add labels."""
        query = "MATCH (c:Cuenta {cuenta_id: $account_id}) SET c.status = $status"
        if labels:
            for label in labels:
                query += f", c:{label}"
        self.execute_cypher(query, {"account_id": account_id, "status": status})

    # ── Private helpers ──

    def _ensure_gds_projection(self, graph_name: str) -> None:
        """Create a GDS graph projection if it doesn't exist."""
        exists = self.execute_cypher(
            "CALL gds.graph.exists($name) YIELD exists RETURN exists",
            {"name": graph_name},
        )
        if not exists or not exists[0].get("exists"):
            self.execute_cypher(f"""
                CALL gds.graph.project(
                    '{graph_name}',
                    ['Cuenta', 'Persona', 'Dispositivo', 'IP'],
                    ['TRANSFIERE_A', 'USA_DISPOSITIVO', 'CONECTA_DESDE_IP', 'ES_TITULAR_DE', 'COMPARTE_DATO_CON']
                )
            """)

    @staticmethod
    def _label_to_node_type(labels: list[str]) -> NodeType:
        mapping = {
            "Persona": NodeType.PERSONA,
            "Cuenta": NodeType.CUENTA,
            "Dispositivo": NodeType.DISPOSITIVO,
            "IP": NodeType.IP,
            "Transaccion": NodeType.TRANSACCION,
            "EntidadExterna": NodeType.ENTIDAD_EXTERNA,
        }
        for label in labels:
            if label in mapping:
                return mapping[label]
        return NodeType.CUENTA

    @staticmethod
    def _rel_to_type(rel_type: str) -> RelationType:
        try:
            return RelationType(rel_type)
        except ValueError:
            return RelationType.COMPARTE_DATO_CON
