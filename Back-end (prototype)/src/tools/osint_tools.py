"""LangChain tools for OSINT investigations."""

from __future__ import annotations

from datetime import datetime

import httpx
import structlog
from langchain_core.tools import tool

from sentinel_swarm.config import get_settings

logger = structlog.get_logger("tools.osint")


@tool
def verify_email(email: str) -> dict:
    """Verify email address: age, provider type, social presence.

    Returns dict with: exists, disposable, age_days, has_social_presence, provider.
    """
    settings = get_settings()
    result = {
        "email": email,
        "exists": True,
        "disposable": False,
        "age_days": None,
        "has_social_presence": False,
        "provider": "unknown",
        "flags": [],
    }

    # Check disposable email providers
    disposable_domains = {
        "tempmail.com", "guerrillamail.com", "mailinator.com", "yopmail.com",
        "throwaway.email", "10minutemail.com", "trashmail.com",
    }
    domain = email.split("@")[-1].lower() if "@" in email else ""
    if domain in disposable_domains:
        result["disposable"] = True
        result["flags"].append("FLAG_DISPOSABLE")

    # In production: use Hunter.io, EmailRep.io, or similar APIs
    # Simulate social presence check
    try:
        with httpx.Client(timeout=5.0) as client:
            # Check if email domain resolves (basic MX check proxy)
            resp = client.get(f"https://emailrep.io/{email}", headers={"Key": "free"})
            if resp.status_code == 200:
                data = resp.json()
                result["has_social_presence"] = data.get("reputation", "none") != "none"
                if not data.get("details", {}).get("profiles", []):
                    result["flags"].append("FLAG_NO_FOOTPRINT")
    except Exception as e:
        logger.warning("email_verification_error", email=email, error=str(e))

    return result


@tool
def phone_intelligence(phone_number: str) -> dict:
    """Check phone number: age, carrier, portability, SIM swap risk.

    Returns dict with: carrier, line_type, ported, sim_swap_recent, age_days.
    """
    # In production: use Twilio Lookup, Telesign, or local telco APIs
    return {
        "phone": phone_number,
        "carrier": "unknown",
        "line_type": "mobile",
        "ported": False,
        "sim_swap_recent": False,
        "age_days": None,
        "flags": [],
    }


@tool
def ip_reputation(ip_address: str) -> dict:
    """Check IP reputation via AbuseIPDB and MaxMind.

    Returns dict with: abuse_score, is_vpn, is_tor, is_proxy, country, reports_count.
    """
    settings = get_settings()
    result = {
        "ip": ip_address,
        "abuse_score": 0,
        "is_vpn": False,
        "is_tor": False,
        "is_proxy": False,
        "country": "unknown",
        "reports_count": 0,
        "flags": [],
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            if settings.abuseipdb_api_key:
                resp = client.get(
                    "https://api.abuseipdb.com/api/v2/check",
                    params={"ipAddress": ip_address, "maxAgeInDays": 90},
                    headers={
                        "Key": settings.abuseipdb_api_key,
                        "Accept": "application/json",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    result["abuse_score"] = data.get("abuseConfidenceScore", 0)
                    result["reports_count"] = data.get("totalReports", 0)
                    result["is_tor"] = data.get("isTor", False)
                    result["country"] = data.get("countryCode", "unknown")

                    if result["is_tor"]:
                        result["flags"].append("FLAG_TOR")
                    if result["abuse_score"] > 50:
                        result["flags"].append("FLAG_HIGH_ABUSE_IP")
    except Exception as e:
        logger.warning("ip_reputation_error", ip=ip_address, error=str(e))

    return result


@tool
def device_intelligence(device_id: str) -> dict:
    """Check device fingerprint reputation.

    Returns dict with: known_fraud, accounts_linked, is_emulator, is_rooted.
    """
    # In production: query internal device fingerprint DB
    return {
        "device_id": device_id,
        "known_fraud": False,
        "accounts_linked": 1,
        "is_emulator": False,
        "is_rooted": False,
        "first_seen": None,
        "flags": [],
    }


@tool
def breach_check(email: str) -> dict:
    """Check if email appears in known data breaches via HIBP.

    Returns dict with: breached, breach_count, breaches.
    """
    settings = get_settings()
    result = {
        "email": email,
        "breached": False,
        "breach_count": 0,
        "breaches": [],
        "flags": [],
    }

    try:
        if settings.hibp_api_key:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                    headers={
                        "hibp-api-key": settings.hibp_api_key,
                        "user-agent": "SentinelSwarm-AROS",
                    },
                    params={"truncateResponse": "true"},
                )
                if resp.status_code == 200:
                    breaches = resp.json()
                    result["breached"] = True
                    result["breach_count"] = len(breaches)
                    result["breaches"] = [b.get("Name", "") for b in breaches[:10]]
    except Exception as e:
        logger.warning("breach_check_error", email=email, error=str(e))

    return result


@tool
def web_search_osint(query: str) -> dict:
    """Perform web search for OSINT context on a subject.

    Returns dict with: results (list of title/url/snippet).
    """
    # In production: use SerpAPI, Google Custom Search, or similar
    return {
        "query": query,
        "results": [],
        "source": "web_search",
    }
