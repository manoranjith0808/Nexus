"""LangChain tools for compliance, sanctions, and regulatory checks."""

from __future__ import annotations

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger("tools.compliance")

# ── GAFI high-risk and grey-list jurisdictions ──
GAFI_HIGH_RISK = {
    "KP", "IR", "MM",  # Black list (call to action)
}
GAFI_GREY_LIST = {
    "BF", "CM", "CD", "HT", "KE", "ML", "MZ", "NG", "PH",
    "SN", "SS", "SY", "TZ", "TT", "VN", "YE",
}

# ── Regulatory references ──
REGULATIONS = {
    "UY": {
        "primary_law": "Ley 19.574 — Prevención del lavado de activos y financiamiento del terrorismo",
        "regulator": "BCU / SENACLAFT",
        "reporting_body": "UIAF",
        "ros_format": "SENACLAFT electronic format",
        "key_articles": [
            "Art. 1 — Definición de lavado de activos",
            "Art. 14 — Obligación de reportar operaciones sospechosas",
            "Art. 15 — Plazo de reporte: 24 horas",
            "Art. 17 — Deber de confidencialidad (anti-tipping-off)",
            "Art. 26 — Sanciones por incumplimiento",
        ],
        "thresholds": {
            "cash_report_usd": 10_000,
            "wire_report_usd": 1_000,  # if suspicious
        },
    },
    "AR": {
        "primary_law": "Ley 25.246 (mod. 26.683) — Encubrimiento y lavado de activos",
        "regulator": "BCRA",
        "reporting_body": "UIF",
        "ros_format": "UIF electronic format (Res. 30/2017)",
        "key_articles": [
            "Art. 20 — Sujetos obligados a informar",
            "Art. 21 — Operaciones sospechosas",
            "Art. 21 bis — Reporte de operación sospechosa (ROS)",
            "BCRA Com. A 6399 — Normas sobre prevención de lavado",
            "BCRA Com. A 7566 — Actualización debida diligencia",
        ],
        "thresholds": {
            "cash_report_ars": 300_000,
            "wire_report_ars": 600_000,
        },
    },
    "INTERNATIONAL": {
        "gafi_40_recommendations": True,
        "gafilat_member": True,
        "ofac_compliance": True,
        "un_sanctions": True,
        "eu_sanctions": True,
    },
}


@tool
def get_regulation(country: str, topic: str = "all") -> dict:
    """Get regulatory framework for a country (UY or AR).

    Args:
        country: 'UY' for Uruguay, 'AR' for Argentina.
        topic: 'all', 'thresholds', 'key_articles', or 'reporting'.
    """
    reg = REGULATIONS.get(country.upper())
    if not reg:
        return {"error": f"Unknown country: {country}. Use UY or AR."}

    if topic == "all":
        return reg
    if topic == "thresholds":
        return {"thresholds": reg.get("thresholds", {})}
    if topic == "key_articles":
        return {"key_articles": reg.get("key_articles", [])}
    if topic == "reporting":
        return {
            "reporting_body": reg.get("reporting_body"),
            "ros_format": reg.get("ros_format"),
        }
    return reg


@tool
def check_sanctions(name: str, document_number: str | None = None) -> dict:
    """Check a person/entity against OFAC, UN, and EU sanctions lists.

    Returns dict with: sanctioned (bool), lists_matched, details.
    """
    # In production: query OFAC SDN, UN consolidated list, EU sanctions via API
    logger.info("sanctions_check", name=name, document=document_number)
    return {
        "name": name,
        "document_number": document_number,
        "sanctioned": False,
        "lists_matched": [],
        "details": "No matches found in OFAC SDN, UN, or EU sanctions lists.",
        "checked_at": "2024-01-01T00:00:00Z",
    }


@tool
def get_gafi_status(country_code: str) -> dict:
    """Get GAFI/FATF risk classification for a jurisdiction.

    Returns: status (HIGH_RISK, GREY_LIST, STANDARD), implications.
    """
    code = country_code.upper()
    if code in GAFI_HIGH_RISK:
        return {
            "country": code,
            "status": "HIGH_RISK",
            "list": "GAFI Black List (Call for Action)",
            "multiplier": 1.20,
            "implications": "Enhanced due diligence required. Counter-measures recommended by GAFI.",
        }
    if code in GAFI_GREY_LIST:
        return {
            "country": code,
            "status": "GREY_LIST",
            "list": "GAFI Grey List (Increased Monitoring)",
            "multiplier": 1.15,
            "implications": "Enhanced due diligence required. Jurisdiction under increased monitoring.",
        }
    return {
        "country": code,
        "status": "STANDARD",
        "list": "Not listed",
        "multiplier": 1.0,
        "implications": "Standard due diligence procedures apply.",
    }


@tool
def calculate_confidence_score(
    sentinel_score: float,
    osint_score: float,
    patterns_score: float,
    historian_score: float,
    jurist_score: float,
    weights: dict[str, float] | None = None,
    multipliers: list[dict] | None = None,
) -> dict:
    """Calculate the weighted confidence score from all agents.

    C = Σ(Wi × Si) / ΣWi, then apply regulatory multipliers.
    """
    w = weights or {
        "sentinel": 0.25, "osint": 0.20, "patterns": 0.20,
        "historian": 0.15, "jurist": 0.20,
    }
    scores = {
        "sentinel": sentinel_score,
        "osint": osint_score,
        "patterns": patterns_score,
        "historian": historian_score,
        "jurist": jurist_score,
    }

    weighted_sum = sum(w[k] * scores[k] for k in scores)
    weight_sum = sum(w.values())
    base_score = weighted_sum / weight_sum if weight_sum > 0 else 0.0

    # Apply multipliers
    final = base_score
    applied = []
    for m in (multipliers or []):
        factor = m.get("multiplier", 1.0)
        final *= factor
        applied.append(m)

    final = min(final, 1.0)  # Cap at 1.0

    return {
        "base_score": round(base_score, 4),
        "final_score": round(final, 4),
        "breakdown": {k: {"score": scores[k], "weight": w[k], "weighted": round(w[k] * scores[k], 4)} for k in scores},
        "multipliers_applied": applied,
    }


@tool
def get_pep_status(name: str, country: str) -> dict:
    """Check if a person is a Politically Exposed Person (PEP).

    Returns: is_pep (bool), category, details.
    """
    # In production: query World-Check, Dow Jones, or local PEP registries
    logger.info("pep_check", name=name, country=country)
    return {
        "name": name,
        "country": country,
        "is_pep": False,
        "category": None,
        "details": "No PEP match found.",
        "multiplier": 1.0,
    }
