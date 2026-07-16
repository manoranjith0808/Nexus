"""Graph data models for Neo4j layer."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(StrEnum):
    PERSONA = "Persona"
    CUENTA = "Cuenta"
    DISPOSITIVO = "Dispositivo"
    IP = "IP"
    TRANSACCION = "Transaccion"
    ENTIDAD_EXTERNA = "EntidadExterna"


class RelationType(StrEnum):
    TRANSFIERE_A = "TRANSFIERE_A"
    USA_DISPOSITIVO = "USA_DISPOSITIVO"
    CONECTA_DESDE_IP = "CONECTA_DESDE_IP"
    ES_TITULAR_DE = "ES_TITULAR_DE"
    COMPARTE_DATO_CON = "COMPARTE_DATO_CON"


class GraphNode(BaseModel):
    """A node in the fraud detection graph."""

    node_id: str
    node_type: NodeType
    properties: dict[str, Any] = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)


class GraphRelation(BaseModel):
    """A relationship in the fraud detection graph."""

    source_id: str
    target_id: str
    relation_type: RelationType
    properties: dict[str, Any] = Field(default_factory=dict)


class SubGraph(BaseModel):
    """A subgraph extracted for analysis."""

    nodes: list[GraphNode] = Field(default_factory=list)
    relations: list[GraphRelation] = Field(default_factory=list)
    center_node_id: str | None = None

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.relations)
