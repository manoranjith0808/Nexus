"""Tests for tool functions."""

from __future__ import annotations

import pytest

from sentinel_swarm.tools.compliance_tools import (
    calculate_confidence_score,
    check_sanctions,
    get_gafi_status,
    get_pep_status,
    get_regulation,
)
from sentinel_swarm.tools.vector_tools import get_case_detail, get_fraud_stats, vector_search


class TestComplianceTools:
    def test_get_regulation_uy(self):
        result = get_regulation.invoke({"country": "UY", "topic": "all"})
        assert result["primary_law"] == "Ley 19.574 — Prevención del lavado de activos y financiamiento del terrorismo"
        assert result["reporting_body"] == "UIAF"

    def test_get_regulation_ar(self):
        result = get_regulation.invoke({"country": "AR", "topic": "all"})
        assert result["reporting_body"] == "UIF"
        assert "BCRA" in result["regulator"]

    def test_get_regulation_thresholds(self):
        result = get_regulation.invoke({"country": "UY", "topic": "thresholds"})
        assert "thresholds" in result
        assert result["thresholds"]["cash_report_usd"] == 10_000

    def test_get_regulation_unknown_country(self):
        result = get_regulation.invoke({"country": "XX"})
        assert "error" in result

    def test_gafi_high_risk(self):
        result = get_gafi_status.invoke({"country_code": "KP"})
        assert result["status"] == "HIGH_RISK"
        assert result["multiplier"] == 1.20

    def test_gafi_grey_list(self):
        result = get_gafi_status.invoke({"country_code": "NG"})
        assert result["status"] == "GREY_LIST"
        assert result["multiplier"] == 1.15

    def test_gafi_standard(self):
        result = get_gafi_status.invoke({"country_code": "UY"})
        assert result["status"] == "STANDARD"
        assert result["multiplier"] == 1.0

    def test_sanctions_check(self):
        result = check_sanctions.invoke({"name": "Test User", "document_number": "123"})
        assert result["sanctioned"] is False

    def test_pep_check(self):
        result = get_pep_status.invoke({"name": "Test User", "country": "UY"})
        assert result["is_pep"] is False

    def test_calculate_score(self):
        result = calculate_confidence_score.invoke({
            "sentinel_score": 0.8,
            "osint_score": 0.6,
            "patterns_score": 0.7,
            "historian_score": 0.5,
            "jurist_score": 0.9,
        })
        assert "base_score" in result
        assert "final_score" in result
        assert 0 <= result["base_score"] <= 1

    def test_calculate_score_with_multipliers(self):
        result = calculate_confidence_score.invoke({
            "sentinel_score": 0.8,
            "osint_score": 0.6,
            "patterns_score": 0.7,
            "historian_score": 0.5,
            "jurist_score": 0.9,
            "multipliers": [{"multiplier": 1.15, "factor": "gafi"}],
        })
        assert result["final_score"] > result["base_score"]


class TestVectorTools:
    def test_vector_search(self):
        results = vector_search.invoke({"query_text": "smurfing attack", "k": 5})
        assert isinstance(results, list)
        assert len(results) <= 5

    def test_vector_search_with_pattern_filter(self):
        results = vector_search.invoke({
            "query_text": "smurfing", "pattern_type": "SMURFING", "k": 10,
        })
        for r in results:
            assert r["pattern"] == "SMURFING"

    def test_get_case_detail_exists(self):
        result = get_case_detail.invoke({"case_id": "HIST-001"})
        assert result["case_id"] == "HIST-001"
        assert result["pattern"] == "SMURFING"

    def test_get_case_detail_not_found(self):
        result = get_case_detail.invoke({"case_id": "NONEXISTENT"})
        assert "error" in result

    def test_fraud_stats(self):
        result = get_fraud_stats.invoke({})
        assert "total_cases" in result
        assert "fraud_rate" in result
        assert result["total_cases"] > 0

    def test_fraud_stats_filtered(self):
        result = get_fraud_stats.invoke({"pattern_type": "SMURFING"})
        assert result["total_cases"] >= 1
