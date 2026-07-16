"""Case state model — the global state object flowing through LangGraph."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from sentinel_swarm.models.agents import (
    AgentReport,
    ExecutorReport,
    HistorianReport,
    JuristReport,
    OSINTReport,
    PatternReport,
    SentinelReport,
    Verdict,
)
from sentinel_swarm.models.events import EnrichedEvent


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    DECIDED = "DECIDED"
    EXECUTED = "EXECUTED"
    CLOSED = "CLOSED"


class CaseState(BaseModel):
    """Global state object that flows through the LangGraph pipeline.

    Each agent reads from and writes to this state.
    """

    case_id: str
    status: CaseStatus = CaseStatus.OPEN
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Input
    enriched_event: EnrichedEvent | None = None

    # Agent reports (6 slots)
    sentinel_report: SentinelReport | None = None
    osint_report: OSINTReport | None = None
    pattern_report: PatternReport | None = None
    historian_report: HistorianReport | None = None
    jurist_report: JuristReport | None = None
    executor_report: ExecutorReport | None = None

    # Consolidated
    verdict: Verdict | None = None
    final_confidence_score: float | None = None

    # Performance
    total_latency_ms: int = 0
    error_log: list[str] = Field(default_factory=list)

    # Bank configuration
    bank_id: str = ""
    country: str = ""  # UY or AR
