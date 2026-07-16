"""Shared training data endpoints.

Cross-tenant anonymized data for model training.
Each tenant's data is isolated, but patterns, topologies, and anonymized
features are shared across tenants to improve detection for everyone.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from sentinel_swarm.api.deps import get_cases_store, get_neo4j

router = APIRouter()


@router.get("/patterns")
async def get_shared_patterns() -> dict:
    """Get anonymized fraud patterns aggregated across all tenants.

    Returns pattern frequencies, modus operandi, and structural signatures
    WITHOUT any PII or tenant-identifying information.
    """
    cases = list(get_cases_store().values())

    patterns: dict[str, int] = {}
    verdicts: dict[str, int] = {}
    scores: list[float] = []
    modus: list[str] = []

    for c in cases:
        v = c.get("verdict") or "DISMISSED"
        verdicts[v] = verdicts.get(v, 0) + 1

        if c.get("final_confidence_score") is not None:
            scores.append(c["final_confidence_score"])

        pr = c.get("pattern_report")
        if pr and pr.get("pattern_match") and pr["pattern_match"].get("pattern_id"):
            pid = pr["pattern_match"]["pattern_id"]
            patterns[pid] = patterns.get(pid, 0) + 1

        hr = c.get("historian_report")
        if hr:
            for prec in hr.get("top_precedents", []):
                if prec.get("modus_operandi"):
                    modus.append(prec["modus_operandi"])

    return {
        "total_cases": len(cases),
        "pattern_distribution": patterns,
        "verdict_distribution": verdicts,
        "avg_confidence_score": round(sum(scores) / len(scores), 4) if scores else 0,
        "modus_operandi_samples": list(set(modus))[:20],
        "anonymized": True,
    }


@router.get("/topology-signatures")
async def get_topology_signatures() -> dict:
    """Get anonymized graph topology signatures across all tenants.

    Returns structural features (degree distributions, clustering coefficients,
    density) that help train the pattern matcher without revealing specific data.
    """
    neo4j = get_neo4j()

    # Aggregate structural features across all tenants
    degree_dist = neo4j.execute_cypher(
        """
        MATCH (c:Cuenta)
        WITH c, size((c)-[:TRANSFIERE_A]->()) AS out_degree,
             size((c)<-[:TRANSFIERE_A]-()) AS in_degree
        RETURN
            avg(out_degree) AS avg_out_degree,
            avg(in_degree) AS avg_in_degree,
            max(out_degree) AS max_out_degree,
            max(in_degree) AS max_in_degree,
            count(c) AS total_accounts
        """
    )

    shared_resources = neo4j.execute_cypher(
        """
        MATCH (d:Dispositivo)<-[:USA_DISPOSITIVO]-(c:Cuenta)
        WITH d, count(DISTINCT c) AS accounts_per_device
        WHERE accounts_per_device > 1
        RETURN count(d) AS shared_devices,
               avg(accounts_per_device) AS avg_accounts_per_shared_device,
               max(accounts_per_device) AS max_accounts_per_shared_device
        """
    )

    return {
        "degree_distribution": degree_dist[0] if degree_dist else {},
        "shared_resources": shared_resources[0] if shared_resources else {},
        "anonymized": True,
        "note": "These are structural features only — no PII or tenant data included.",
    }


@router.get("/risk-features")
async def get_risk_features(
    tenant_id: str | None = Query(None, description="Optional: filter by tenant"),
) -> dict:
    """Get anonymized risk feature vectors for model training.

    Returns feature distributions (amounts, velocities, flag frequencies)
    aggregated across cases. When tenant_id is provided, returns features
    for that tenant only (for local model fine-tuning).
    """
    cases = list(get_cases_store().values())
    if tenant_id:
        cases = [c for c in cases if c.get("tenant_id") == tenant_id]

    features = {
        "amounts": [],
        "latencies": [],
        "sentinel_scores": [],
        "osint_scores": [],
        "pattern_scores": [],
        "historian_scores": [],
        "flag_frequencies": {},
    }

    for c in cases:
        event = c.get("enriched_event", {})
        if isinstance(event, dict):
            evt = event.get("event", {})
            if isinstance(evt, dict) and evt.get("amount"):
                features["amounts"].append(evt["amount"])

        features["latencies"].append(c.get("total_latency_ms", 0))

        sr = c.get("sentinel_report")
        if sr:
            features["sentinel_scores"].append(sr.get("risk_score", 0))

        osr = c.get("osint_report")
        if osr:
            features["osint_scores"].append(osr.get("risk_score", 0))
            for flag in osr.get("flags", []):
                features["flag_frequencies"][flag] = features["flag_frequencies"].get(flag, 0) + 1

        pr = c.get("pattern_report")
        if pr:
            features["pattern_scores"].append(pr.get("risk_score", 0))

        hr = c.get("historian_report")
        if hr:
            features["historian_scores"].append(hr.get("risk_score", 0))

    # Compute stats instead of raw values
    def stats(arr: list[float]) -> dict:
        if not arr:
            return {"count": 0, "mean": 0, "min": 0, "max": 0}
        return {
            "count": len(arr),
            "mean": round(sum(arr) / len(arr), 4),
            "min": round(min(arr), 4),
            "max": round(max(arr), 4),
        }

    return {
        "case_count": len(cases),
        "amount_stats": stats(features["amounts"]),
        "latency_stats": stats(features["latencies"]),
        "sentinel_score_stats": stats(features["sentinel_scores"]),
        "osint_score_stats": stats(features["osint_scores"]),
        "pattern_score_stats": stats(features["pattern_scores"]),
        "historian_score_stats": stats(features["historian_scores"]),
        "flag_frequencies": features["flag_frequencies"],
        "tenant_scoped": tenant_id is not None,
        "anonymized": tenant_id is None,
    }


@router.get("/cross-tenant/correlations")
async def cross_tenant_correlations() -> dict:
    """Find correlations and shared indicators across tenants.

    Identifies IPs, devices, or behavioral patterns that appear in
    fraud cases across multiple banks. Critical for detecting
    organized cross-bank fraud rings.
    """
    neo4j = get_neo4j()

    # IPs used across multiple tenants
    shared_ips = neo4j.execute_cypher(
        """
        MATCH (c:Cuenta)-[:CONECTA_DESDE_IP]->(ip:IP)
        WITH ip, collect(DISTINCT c.tenant_id) AS tenants, count(DISTINCT c) AS account_count
        WHERE size(tenants) > 1
        RETURN ip.address AS ip,
               tenants,
               account_count,
               ip.is_vpn AS is_vpn,
               ip.is_tor AS is_tor
        ORDER BY account_count DESC
        LIMIT 50
        """
    )

    # Devices used across multiple tenants
    shared_devices = neo4j.execute_cypher(
        """
        MATCH (c:Cuenta)-[:USA_DISPOSITIVO]->(d:Dispositivo)
        WITH d, collect(DISTINCT c.tenant_id) AS tenants, count(DISTINCT c) AS account_count
        WHERE size(tenants) > 1
        RETURN d.device_id AS device_id,
               tenants,
               account_count,
               d.known_fraud AS known_fraud
        ORDER BY account_count DESC
        LIMIT 50
        """
    )

    return {
        "cross_tenant_ips": shared_ips,
        "cross_tenant_devices": shared_devices,
        "ip_count": len(shared_ips),
        "device_count": len(shared_devices),
        "note": "These indicators appear across multiple banks — high likelihood of organized fraud.",
    }
