"""Centralized configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # ── Neo4j ──
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "sentinel_swarm_2024"

    # ── Kafka ──
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_events: str = "banking.events"
    kafka_topic_alerts: str = "sentinel.alerts"
    kafka_consumer_group: str = "sentinel-swarm"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── LLM ──
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llama_base_url: str = "http://localhost:8080/v1"
    llama_model: str = "llama-3-70b"

    # ── OSINT APIs ──
    abuseipdb_api_key: str = ""
    maxmind_license_key: str = ""
    hibp_api_key: str = ""

    # ── Prometeo Open Banking ──
    prometeo_api_key: str = ""
    prometeo_sandbox: bool = True

    # ── Thresholds ──
    threshold_sentinel: float = 0.30
    threshold_block: float = 0.85
    threshold_escalate: float = 0.65
    threshold_monitor: float = 0.40
    max_latency_total_ms: int = 15_000
    monitoring_hours: int = 72

    # ── Agent weights ──
    weight_sentinel: float = 0.25
    weight_osint: float = 0.20
    weight_patterns: float = 0.20
    weight_historian: float = 0.15
    weight_jurist: float = 0.20

    # ── Operational ──
    ros_auto_submit: bool = True
    parallel_agents: bool = True
    log_level: str = "INFO"
    environment: str = "development"

    # ── Timeouts (seconds) ──
    timeout_sentinel: int = 3
    timeout_osint: int = 7
    timeout_patterns: int = 5
    timeout_historian: int = 5
    timeout_jurist: int = 8
    timeout_executor: int = 5

    @property
    def agent_weights(self) -> dict[str, float]:
        return {
            "sentinel": self.weight_sentinel,
            "osint": self.weight_osint,
            "patterns": self.weight_patterns,
            "historian": self.weight_historian,
            "jurist": self.weight_jurist,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
