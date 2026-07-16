"""Data models for all 6 agent reports and inter-agent communication."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from sentinel_swarm.models.graph import SubGraph


# ── Enums ──


class Verdict(StrEnum):
    DISCARD = "DISCARD"
    MONITOR = "MONITOR"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"


class IdentityAssessment(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    SYNTHETIC_PROBABLE = "SYNTHETIC_PROBABLE"


class PatternMatchStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class PatternScale(StrEnum):
    INDIVIDUAL_ATTACKER = "INDIVIDUAL_ATTACKER"
    SMALL_NETWORK = "SMALL_NETWORK"
    ORGANIZED_RING = "ORGANIZED_RING"


class NodeRole(StrEnum):
    SOURCE = "SOURCE"
    MULE = "MULE"
    CONSOLIDATOR = "CONSOLIDATOR"
    BRIDGE = "BRIDGE"


class ROSDestination(StrEnum):
    UIAF_UY = "UIAF_UY"
    UIF_AR = "UIF_AR"
    BOTH = "BOTH"


class PatternType(StrEnum):
    SMURFING = "SMURFING"
    ACCOUNT_TAKEOVER = "ACCOUNT_TAKEOVER"
    SYNTHETIC_IDENTITY = "IDENTIDAD_SINTETICA"
    LAYERING = "LAYERING"
    INSURANCE_FRAUD = "FRAUDE_SEGUROS"
    CARD_CAROUSEL = "CARRUSEL_TARJETAS"
    ROUND_TRIPPING = "ROUND_TRIPPING"


# ── Base Agent Report ──


class AgentReport(BaseModel):
    """Base schema for inter-agent communication."""

    agent_id: str
    case_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    risk_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    findings: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    recommendation: str = ""
    next_agent: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = 0
    error: str | None = None


# ── Agent 1: El Centinela ──


class SentinelFinding(BaseModel):
    pattern_detected: str
    description: str
    affected_nodes: list[str] = Field(default_factory=list)
    severity: float = Field(ge=0.0, le=1.0)


class SentinelReport(AgentReport):
    """Output from Agent 1 — El Centinela."""

    agent_id: str = "sentinel"
    pattern_detected: str = ""
    suspect_nodes: list[str] = Field(default_factory=list)
    subgraph: SubGraph | None = None
    detailed_findings: list[SentinelFinding] = Field(default_factory=list)
    risk_multipliers_applied: dict[str, float] = Field(default_factory=dict)


# ── Agent 2: El Investigador OSINT ──


class OSINTFlag(BaseModel):
    flag_id: str
    description: str
    penalty: float = Field(ge=0.0, le=1.0)
    source: str = ""


class OSINTReport(AgentReport):
    """Output from Agent 2 — El Investigador OSINT."""

    agent_id: str = "osint"
    identity_assessment: IdentityAssessment = IdentityAssessment.UNVERIFIED
    legitimacy_score: float = Field(1.0, ge=0.0, le=1.0)
    osint_flags: list[OSINTFlag] = Field(default_factory=list)
    narrative_summary: str = ""
    email_verified: bool | None = None
    phone_verified: bool | None = None
    ip_reputation_score: float | None = None


# ── Agent 3: El Arquitecto de Patrones ──


class PatternMatch(BaseModel):
    pattern_id: PatternType
    similarity_pct: float = Field(ge=0.0, le=100.0)
    match_status: PatternMatchStatus
    description: str = ""


class CriticalNode(BaseModel):
    node_id: str
    role: NodeRole
    centrality_score: float = 0.0


class PatternReport(AgentReport):
    """Output from Agent 3 — El Arquitecto de Patrones."""

    agent_id: str = "patterns"
    pattern_match: PatternMatch | None = None
    scale_assessment: PatternScale | None = None
    critical_nodes: list[CriticalNode] = Field(default_factory=list)
    topology_summary: str = ""


# ── Agent 4: El Historiador Forense ──


class Precedent(BaseModel):
    case_id: str
    similarity_pct: float
    result: str  # FRAUD_CONFIRMED / FALSE_POSITIVE
    action_taken: str
    losses_usd: float = 0.0
    regulatory_resolution: str = ""
    modus_operandi: str = ""


class HistorianReport(AgentReport):
    """Output from Agent 4 — El Historiador Forense."""

    agent_id: str = "historian"
    top_precedents: list[Precedent] = Field(default_factory=list)
    historical_fraud_rate: float = Field(0.0, ge=0.0, le=1.0)
    precedent_count: int = 0
    lessons_learned: list[str] = Field(default_factory=list)
    narrative_summary: str = ""


# ── Agent 5: El Jurista de Compliance ──


class ScoreBreakdown(BaseModel):
    agent: str
    raw_score: float
    weight: float
    weighted_score: float


class RegulatoryMultiplier(BaseModel):
    factor: str
    multiplier: float
    reason: str


class LegalJustification(BaseModel):
    applicable_norms: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    reasoning: str = ""
    proportionality: str = ""
    inaction_risk: str = ""


class JuristReport(AgentReport):
    """Output from Agent 5 — El Jurista de Compliance."""

    agent_id: str = "jurist"
    verdict: Verdict = Verdict.DISCARD
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    score_breakdown: list[ScoreBreakdown] = Field(default_factory=list)
    regulatory_multipliers: list[RegulatoryMultiplier] = Field(default_factory=list)
    legal_justification: LegalJustification | None = None
    actions_ordered: list[str] = Field(default_factory=list)
    ros_required: bool = False
    ros_destination: ROSDestination | None = None


# ── Agent 6: El Ejecutor ──


class ActionResult(BaseModel):
    action: str
    status: str  # SUCCESS / FAILED / SKIPPED
    rollback_id: str | None = None
    details: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ROSDocument(BaseModel):
    ros_id: str
    destination: ROSDestination
    subject_data: dict[str, Any] = Field(default_factory=dict)
    operation_description: str = ""
    suspicion_grounds: str = ""
    supporting_docs: list[str] = Field(default_factory=list)
    action_taken: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutorReport(AgentReport):
    """Output from Agent 6 — El Ejecutor."""

    agent_id: str = "executor"
    execution_status: str = "PENDING"
    actions_executed: list[ActionResult] = Field(default_factory=list)
    ros_generated: ROSDocument | None = None
    notifications_sent: list[str] = Field(default_factory=list)
    graph_updated: bool = False
    errors: list[str] = Field(default_factory=list)
