"""Seed script — populates Sentinel Swarm with realistic test data.

Creates:
- 3 banks (2 UY, 1 AR)
- ~40 accounts with personas, devices, IPs
- Transfer networks including fraud rings, smurfing, and clean activity
- Processes suspicious events through the pipeline

Usage:
    source .venv/bin/activate
    python seed.py
"""

import asyncio
import json
import random
import time
import uuid
from datetime import datetime, timedelta

import httpx

API = "http://localhost:3000"
client = httpx.Client(base_url=API, timeout=60.0)


# ══════════════════════════════════════════════
# 1. CREATE BANKS
# ══════════════════════════════════════════════

BANKS = [
    {
        "name": "Banco República (BROU)",
        "country": "UY",
        "regulatory_id": "BCU-0001",
        "compliance_officer": "María Fernández",
        "compliance_email": "compliance@brou.com.uy",
    },
    {
        "name": "Banco Itaú Uruguay",
        "country": "UY",
        "regulatory_id": "BCU-0042",
        "compliance_officer": "Santiago Rodríguez",
        "compliance_email": "compliance@itau.com.uy",
    },
    {
        "name": "Banco Nación Argentina",
        "country": "AR",
        "regulatory_id": "BCRA-0044",
        "compliance_officer": "Luciana Martínez",
        "compliance_email": "compliance@bna.com.ar",
    },
]


# ══════════════════════════════════════════════
# 2. ACCOUNT DATA — mix of clean and suspicious
# ══════════════════════════════════════════════

# Uruguay accounts
UY_CLEAN_ACCOUNTS = [
    {"account_id": "UY-C001", "user_id": "UY-U001", "name": "Roberto Pérez", "doc": "1.234.567-8", "email": "roberto.perez@gmail.com", "device": "DEV-IPHONE14-001", "ip": "190.64.100.12"},
    {"account_id": "UY-C002", "user_id": "UY-U002", "name": "Ana García", "doc": "2.345.678-9", "email": "ana.garcia@hotmail.com", "device": "DEV-SAMSUNG-002", "ip": "190.64.101.33"},
    {"account_id": "UY-C003", "user_id": "UY-U003", "name": "Carlos Martínez", "doc": "3.456.789-0", "email": "carlos.martinez@adinet.com.uy", "device": "DEV-PIXEL-003", "ip": "190.64.102.55"},
    {"account_id": "UY-C004", "user_id": "UY-U004", "name": "Laura Rodríguez", "doc": "4.567.890-1", "email": "laura.rod@outlook.com", "device": "DEV-IPHONE15-004", "ip": "167.56.10.88"},
    {"account_id": "UY-C005", "user_id": "UY-U005", "name": "Diego Silva", "doc": "5.678.901-2", "email": "diego.silva@gmail.com", "device": "DEV-MACBOOK-005", "ip": "167.56.11.44"},
    {"account_id": "UY-C006", "user_id": "UY-U006", "name": "Valentina López", "doc": "6.789.012-3", "email": "valentina.lopez@gmail.com", "device": "DEV-IPAD-006", "ip": "190.64.103.77"},
    {"account_id": "UY-C007", "user_id": "UY-U007", "name": "Martín Fernández", "doc": "7.890.123-4", "email": "martin.f@yahoo.com", "device": "DEV-SAMSUNG-007", "ip": "167.56.12.99"},
    {"account_id": "UY-C008", "user_id": "UY-U008", "name": "Sofía Hernández", "doc": "8.901.234-5", "email": "sofia.h@gmail.com", "device": "DEV-IPHONE13-008", "ip": "190.64.104.22"},
]

# Fraud ring accounts — SMURFING NETWORK (same devices/IPs, temp emails)
UY_SMURFING = [
    {"account_id": "UY-MULA01", "user_id": "UY-MU01", "name": "Persona Falsa 1", "doc": "9.111.111-1", "email": "j39fk2@tempmail.com", "device": "DEV-BURNER-X01", "ip": "185.220.101.45"},
    {"account_id": "UY-MULA02", "user_id": "UY-MU02", "name": "Persona Falsa 2", "doc": "9.222.222-2", "email": "k48gl3@guerrillamail.com", "device": "DEV-BURNER-X01", "ip": "185.220.101.45"},  # SAME device+IP!
    {"account_id": "UY-MULA03", "user_id": "UY-MU03", "name": "Persona Falsa 3", "doc": "9.333.333-3", "email": "m57hk4@yopmail.com", "device": "DEV-BURNER-X02", "ip": "185.220.101.45"},  # SAME IP!
    {"account_id": "UY-MULA04", "user_id": "UY-MU04", "name": "Persona Falsa 4", "doc": "9.444.444-4", "email": "n66ij5@tempmail.com", "device": "DEV-BURNER-X02", "ip": "185.220.101.46"},
    {"account_id": "UY-CONSOL", "user_id": "UY-CON01", "name": "Consolidador Central", "doc": "9.555.555-5", "email": "consolidator@protonmail.com", "device": "DEV-BURNER-X03", "ip": "45.33.32.156"},
]

# Account takeover target
UY_ATO_VICTIM = {"account_id": "UY-ATO01", "user_id": "UY-ATOV", "name": "Víctima ATO", "doc": "1.111.222-3", "email": "victima.real@gmail.com", "device": "DEV-IPHONE-ATO", "ip": "190.64.200.10"}

# Argentina accounts
AR_ACCOUNTS = [
    {"account_id": "AR-C001", "user_id": "AR-U001", "name": "Juan Pablo Ramírez", "doc": "30.123.456", "email": "jpramirez@gmail.com", "device": "DEV-XIAOMI-AR01", "ip": "200.45.100.11"},
    {"account_id": "AR-C002", "user_id": "AR-U002", "name": "María José Díaz", "doc": "31.234.567", "email": "mjdiaz@outlook.com", "device": "DEV-SAMSUNG-AR02", "ip": "200.45.101.22"},
    {"account_id": "AR-C003", "user_id": "AR-U003", "name": "Pedro Sánchez", "doc": "32.345.678", "email": "psanchez@yahoo.com.ar", "device": "DEV-MOTO-AR03", "ip": "200.45.102.33"},
    {"account_id": "AR-C004", "user_id": "AR-U004", "name": "Florencia Torres", "doc": "33.456.789", "email": "ftorres@gmail.com", "device": "DEV-IPHONE-AR04", "ip": "200.45.103.44"},
    {"account_id": "AR-C005", "user_id": "AR-U005", "name": "Ricardo Gómez", "doc": "34.567.890", "email": "rgomez@live.com.ar", "device": "DEV-PIXEL-AR05", "ip": "200.45.104.55"},
    # AR suspicious — round-tripping
    {"account_id": "AR-SUS01", "user_id": "AR-SU01", "name": "Empresa Fantasma SA", "doc": "20-99887766-3", "email": "admin@empresafantasma.com.ar", "device": "DEV-OLD-LAPTOP", "ip": "181.46.200.1"},
    {"account_id": "AR-SUS02", "user_id": "AR-SU02", "name": "Offshore Holdings LLC", "doc": "27-11223344-5", "email": "info@offshorehold.com", "device": "DEV-OLD-LAPTOP", "ip": "181.46.200.1"},  # SAME device+IP
]


# ══════════════════════════════════════════════
# 3. SEED FUNCTIONS
# ══════════════════════════════════════════════


def create_banks() -> dict[str, str]:
    """Create banks and return {name_key: tenant_id}."""
    print("\n🏦 Creating banks...")
    tenant_ids = {}
    for bank in BANKS:
        resp = client.post("/api/tenants/", json=bank)
        data = resp.json()
        key = bank["country"] + ("1" if "República" in bank["name"] or "Nación" in bank["name"] else "2")
        tenant_ids[key] = data["tenant_id"]
        print(f"  ✅ {data['name']} → {data['tenant_id']}")
    return tenant_ids


def seed_clean_transfers(tenant_id: str, accounts: list[dict], country: str, doc_type: str):
    """Create normal, legitimate banking activity."""
    print(f"\n💳 Seeding clean transfers for {country}...")
    clean_scenarios = [
        # Regular salary deposits
        {"src": 0, "dst": 1, "amount": 2500, "type": "transfer"},
        {"src": 1, "dst": 2, "amount": 800, "type": "transfer"},
        {"src": 2, "dst": 3, "amount": 1200, "type": "transfer"},
        {"src": 3, "dst": 4, "amount": 500, "type": "transfer"},
        # Normal logins
        {"src": 0, "dst": 0, "amount": 0, "type": "login"},
        {"src": 1, "dst": 1, "amount": 0, "type": "login"},
        {"src": 2, "dst": 2, "amount": 0, "type": "login"},
        {"src": 3, "dst": 3, "amount": 0, "type": "balance_inquiry"},
        # Small transfers
        {"src": 4, "dst": 0, "amount": 350, "type": "transfer"},
        {"src": 0, "dst": 3, "amount": 1800, "type": "transfer"},
        {"src": 5, "dst": 6, "amount": 4200, "type": "transfer"} if len(accounts) > 6 else {"src": 0, "dst": 1, "amount": 150, "type": "transfer"},
        {"src": 1, "dst": 4, "amount": 950, "type": "transfer"},
    ]

    for s in clean_scenarios:
        src = accounts[s["src"]]
        dst = accounts[s["dst"]] if s["dst"] != s["src"] else src
        event = {
            "tenant_id": tenant_id,
            "account_id": src["account_id"],
            "user_id": src["user_id"],
            "event_type": s["type"],
            "amount": s["amount"] if s["amount"] > 0 else None,
            "currency": "USD",
            "destination_account": dst["account_id"] if s["type"] == "transfer" else None,
            "destination_country": country,
            "ip_address": src["ip"],
            "device_id": src["device"],
            "document_type": doc_type,
            "document_number": src["doc"],
            "email": src["email"],
            "name": src["name"],
            "is_vpn": False,
            "is_tor": False,
            "events_last_1h": random.randint(0, 3),
            "events_last_24h": random.randint(2, 8),
            "total_amount_24h": random.uniform(500, 5000),
        }
        resp = client.post("/api/events/process", json=event)
        data = resp.json()
        v = data.get("verdict") or "—"
        print(f"  {'✅' if v in ('DISCARD', None, '—') else '⚠️'} {src['name'][:20]:20s} → {dst['name'][:20]:20s}  ${s['amount']:>8,.0f}  [{s['type']:15s}] → {v}")


def seed_smurfing_ring(tenant_id: str, mulas: list[dict]):
    """Create a smurfing (structuring) fraud ring."""
    print(f"\n🚨 Seeding SMURFING ring...")

    # Step 1: Each mula receives small amounts just under reporting threshold
    for i, mula in enumerate(mulas[:-1]):
        event = {
            "tenant_id": tenant_id,
            "account_id": mula["account_id"],
            "user_id": mula["user_id"],
            "event_type": "transfer",
            "amount": random.uniform(8000, 9900),  # Just under $10K
            "currency": "USD",
            "destination_account": mulas[-1]["account_id"],  # All go to consolidator
            "destination_country": "UY",
            "ip_address": mula["ip"],
            "device_id": mula["device"],
            "document_type": "cedula",
            "document_number": mula["doc"],
            "email": mula["email"],
            "name": mula["name"],
            "is_vpn": True,
            "is_tor": "185.220" in mula["ip"],
            "events_last_1h": random.randint(5, 15),
            "events_last_24h": random.randint(20, 50),
            "total_amount_24h": random.uniform(15000, 40000),
            "password_changes_7d": random.randint(1, 3),
        }
        resp = client.post("/api/events/process", json=event)
        data = resp.json()
        v = data.get("verdict") or "—"
        score = data.get("final_confidence_score") or 0
        print(f"  🔴 MULA {i+1} → CONSOLIDADOR  ${event['amount']:>8,.0f}  score={score:.4f} → {v}")

    # Step 2: Consolidator sends large amount offshore
    consol = mulas[-1]
    event = {
        "tenant_id": tenant_id,
        "account_id": consol["account_id"],
        "user_id": consol["user_id"],
        "event_type": "transfer",
        "amount": 35000,
        "currency": "USD",
        "destination_account": "OFFSHORE-CAYMAN-001",
        "destination_country": "KY",  # Cayman Islands - GAFI
        "ip_address": consol["ip"],
        "device_id": consol["device"],
        "document_type": "cedula",
        "document_number": consol["doc"],
        "email": consol["email"],
        "name": consol["name"],
        "is_vpn": True,
        "is_tor": False,
        "events_last_1h": 8,
        "events_last_24h": 30,
        "total_amount_24h": 70000,
        "password_changes_7d": 2,
    }
    resp = client.post("/api/events/process", json=event)
    data = resp.json()
    v = data.get("verdict") or "—"
    score = data.get("final_confidence_score") or 0
    print(f"  🔴 CONSOLIDADOR → OFFSHORE     ${35000:>8,.0f}  score={score:.4f} → {v}")


def seed_account_takeover(tenant_id: str, victim: dict):
    """Simulate account takeover attack chain."""
    print(f"\n🚨 Seeding ACCOUNT TAKEOVER...")

    # Step 1: New device linked (attacker's device)
    event_base = {
        "tenant_id": tenant_id,
        "account_id": victim["account_id"],
        "user_id": victim["user_id"],
        "document_type": "cedula",
        "document_number": victim["doc"],
        "email": victim["email"],
        "name": victim["name"],
    }

    # Device link from suspicious IP
    event1 = {**event_base, "event_type": "device_link", "ip_address": "91.219.237.10", "device_id": "DEV-ATTACKER-001", "is_vpn": True, "is_tor": True, "events_last_1h": 1, "events_last_24h": 1}
    resp = client.post("/api/events/process", json=event1)
    data = resp.json()
    print(f"  🔴 Step 1: device_link from TOR → {(data.get('verdict') or '—')} (score={(data.get('final_confidence_score') or 0):.4f})")

    # Password change
    event2 = {**event_base, "event_type": "password_change", "ip_address": "91.219.237.10", "device_id": "DEV-ATTACKER-001", "is_vpn": True, "is_tor": True, "events_last_1h": 2, "events_last_24h": 2, "password_changes_7d": 1}
    resp = client.post("/api/events/process", json=event2)
    data = resp.json()
    print(f"  🔴 Step 2: password_change      → {(data.get('verdict') or '—')} (score={(data.get('final_confidence_score') or 0):.4f})")

    # Large transfer out
    event3 = {
        **event_base, "event_type": "transfer", "amount": 45000, "currency": "USD",
        "destination_account": "AR-UNKNOWN-999", "destination_country": "AR",
        "ip_address": "91.219.237.10", "device_id": "DEV-ATTACKER-001",
        "is_vpn": True, "is_tor": True,
        "events_last_1h": 3, "events_last_24h": 3,
        "total_amount_24h": 45000, "password_changes_7d": 1,
    }
    resp = client.post("/api/events/process", json=event3)
    data = resp.json()
    print(f"  🔴 Step 3: transfer $45,000     → {(data.get('verdict') or '—')} (score={(data.get('final_confidence_score') or 0):.4f})")


def seed_round_tripping(tenant_id: str, accounts: list[dict]):
    """Simulate round-tripping between AR suspicious accounts."""
    print(f"\n🚨 Seeding ROUND TRIPPING...")

    pairs = [(0, 1), (1, 0), (0, 1), (1, 0)]  # Circular transfers
    for i, (src_idx, dst_idx) in enumerate(pairs):
        src = accounts[src_idx]
        dst = accounts[dst_idx]
        amount = random.uniform(20000, 50000)
        event = {
            "tenant_id": tenant_id,
            "account_id": src["account_id"],
            "user_id": src["user_id"],
            "event_type": "transfer",
            "amount": amount,
            "currency": "USD",
            "destination_account": dst["account_id"],
            "destination_country": "AR",
            "ip_address": src["ip"],
            "device_id": src["device"],
            "document_type": "DNI",
            "document_number": src["doc"],
            "email": src["email"],
            "name": src["name"],
            "is_vpn": True,
            "is_tor": False,
            "events_last_1h": 4 + i,
            "events_last_24h": 15 + i * 3,
            "total_amount_24h": 80000 + (i * 20000),
        }
        resp = client.post("/api/events/process", json=event)
        data = resp.json()
        v = data.get("verdict") or "—"
        score = data.get("final_confidence_score") or 0
        print(f"  🔴 {src['name'][:25]:25s} → {dst['name'][:25]:25s}  ${amount:>10,.0f}  score={score:.4f} → {v}")


def seed_cross_bank_transfers(uy_tid: str, ar_tid: str):
    """Create legitimate cross-bank/cross-country transfers."""
    print(f"\n🌐 Seeding cross-bank transfers...")

    # UY → AR legitimate
    event = {
        "tenant_id": uy_tid,
        "account_id": "UY-C001",
        "user_id": "UY-U001",
        "event_type": "transfer",
        "amount": 3500,
        "currency": "USD",
        "destination_account": "AR-C001",
        "destination_country": "AR",
        "ip_address": "190.64.100.12",
        "device_id": "DEV-IPHONE14-001",
        "document_type": "cedula",
        "document_number": "1.234.567-8",
        "email": "roberto.perez@gmail.com",
        "name": "Roberto Pérez",
    }
    resp = client.post("/api/events/process", json=event)
    data = resp.json()
    print(f"  ✅ UY Roberto Pérez → AR Juan Pablo Ramírez  $3,500  → {(data.get('verdict') or '—')}")

    # AR → UY legitimate
    event2 = {
        "tenant_id": ar_tid,
        "account_id": "AR-C002",
        "user_id": "AR-U002",
        "event_type": "transfer",
        "amount": 5200,
        "currency": "USD",
        "destination_account": "UY-C004",
        "destination_country": "UY",
        "ip_address": "200.45.101.22",
        "device_id": "DEV-SAMSUNG-AR02",
        "document_type": "DNI",
        "document_number": "31.234.567",
        "email": "mjdiaz@outlook.com",
        "name": "María José Díaz",
    }
    resp = client.post("/api/events/process", json=event2)
    data = resp.json()
    print(f"  ✅ AR María José Díaz → UY Laura Rodríguez  $5,200  → {(data.get('verdict') or '—')}")


def print_summary():
    """Print summary of all processed data."""
    print("\n" + "=" * 70)
    print("📊 RESUMEN FINAL")
    print("=" * 70)

    # Tenants
    tenants = client.get("/api/tenants/").json()
    print(f"\n🏦 Bancos: {len(tenants)}")
    for t in tenants:
        print(f"  {t['tenant_id']}: {t['name']} ({t['country']}) — {t.get('total_cases', 0)} cases, {t.get('total_alerts', 0)} alerts, {t.get('total_blocked', 0)} blocked")

    # Cases summary
    stats = client.get("/api/cases/stats/summary").json()
    print(f"\n📋 Casos totales: {stats['total']}")
    print(f"  Verdicts: {stats['verdicts']}")
    print(f"  Avg score: {stats['avg_score']}")
    print(f"  Avg latency: {stats['avg_latency_ms']}ms")

    # Training data
    patterns = client.get("/api/training/patterns").json()
    print(f"\n🧠 Training data:")
    print(f"  Pattern distribution: {patterns['pattern_distribution']}")
    print(f"  Verdict distribution: {patterns['verdict_distribution']}")

    # Graph stats per tenant
    print(f"\n🕸️ Graph stats:")
    for t in tenants:
        stats = client.get(f"/api/tenants/{t['tenant_id']}/stats").json()
        graph = stats.get("graph", {})
        print(f"  {t['name']}:")
        for n in graph.get("nodes", []):
            print(f"    {n['tipo']}: {n['cantidad']}")
        for r in graph.get("relations", []):
            print(f"    [{r['tipo']}]: {r['cantidad']}")


# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

def main():
    start = time.time()
    print("🛡️  SENTINEL SWARM — Seed Script")
    print("=" * 70)

    # Check API health
    health = client.get("/health").json()
    print(f"API: {health['status']} | Neo4j: {health['services']['neo4j']}")
    if health["services"]["neo4j"] != "connected":
        print("❌ Neo4j not connected. Run: docker compose -f docker/docker-compose.yml up -d")
        return

    # 1. Create banks
    tids = create_banks()
    uy1 = tids["UY1"]  # BROU
    uy2 = tids["UY2"]  # Itaú
    ar1 = tids["AR1"]  # Nación

    # 2. Clean transfers — BROU
    seed_clean_transfers(uy1, UY_CLEAN_ACCOUNTS, "UY", "cedula")

    # 3. Clean transfers — Itaú (subset of accounts)
    itau_accounts = [
        {"account_id": "UY-IT01", "user_id": "UY-ITU01", "name": "Federico Olivera", "doc": "1.555.666-7", "email": "fede.olivera@gmail.com", "device": "DEV-IPHONE-IT01", "ip": "190.64.150.10"},
        {"account_id": "UY-IT02", "user_id": "UY-ITU02", "name": "Camila Vázquez", "doc": "2.666.777-8", "email": "camila.v@outlook.com", "device": "DEV-SAMSUNG-IT02", "ip": "190.64.150.20"},
        {"account_id": "UY-IT03", "user_id": "UY-ITU03", "name": "Gonzalo Díaz", "doc": "3.777.888-9", "email": "gonzalo.diaz@antel.com.uy", "device": "DEV-PIXEL-IT03", "ip": "190.64.150.30"},
        {"account_id": "UY-IT04", "user_id": "UY-ITU04", "name": "Lucía Sosa", "doc": "4.888.999-0", "email": "lucia.sosa@gmail.com", "device": "DEV-MACBOOK-IT04", "ip": "167.56.50.40"},
        {"account_id": "UY-IT05", "user_id": "UY-ITU05", "name": "Matías Acosta", "doc": "5.999.000-1", "email": "matias.a@yahoo.com", "device": "DEV-IPHONE-IT05", "ip": "167.56.50.50"},
    ]
    seed_clean_transfers(uy2, itau_accounts, "UY", "cedula")

    # 4. Clean transfers — Nación AR
    seed_clean_transfers(ar1, AR_ACCOUNTS[:5], "AR", "DNI")

    # 5. FRAUD: Smurfing ring on BROU
    seed_smurfing_ring(uy1, UY_SMURFING)

    # 6. FRAUD: Account takeover on BROU
    seed_account_takeover(uy1, UY_ATO_VICTIM)

    # 7. FRAUD: Round-tripping on Nación AR
    seed_round_tripping(ar1, AR_ACCOUNTS[5:7])

    # 8. Cross-bank transfers
    seed_cross_bank_transfers(uy1, ar1)

    # Summary
    print_summary()

    elapsed = time.time() - start
    print(f"\n⏱️  Seed completed in {elapsed:.1f}s")
    print(f"\n📡 API: {API}")
    print(f"📊 Swagger: {API}/docs")
    print(f"🕸️ Neo4j: http://localhost:7474")


if __name__ == "__main__":
    main()
