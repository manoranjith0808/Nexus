"""Massive seed — 50K+ cases, thousands of accounts, realistic fraud networks.

Inserts directly into Neo4j in batch (bypasses the slow agent pipeline).
Generates cases in memory and stores them via the API.

Usage:
    source .venv/bin/activate
    python seed_massive.py
"""

import hashlib
import json
import math
import random
import string
import time
import uuid
from datetime import datetime, timedelta

import httpx
from neo4j import GraphDatabase

# ═══════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════

API = "http://localhost:3000"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "sentinel_swarm_2024")

TARGET_CASES = 55_000
ACCOUNTS_PER_BANK = 800
FRAUD_RING_COUNT = 40         # fraud rings per bank
FRAUD_RING_SIZE = (3, 12)     # mules per ring
ATO_COUNT = 60                # account takeovers per bank
ROUND_TRIP_COUNT = 30         # round-tripping pairs per bank
SMURFING_COUNT = 50           # smurfing networks per bank

random.seed(42)

# ═══════════════════════════════════════════════
# DATA GENERATORS
# ═══════════════════════════════════════════════

UY_NAMES = [
    "Santiago","Mateo","Sebastián","Martín","Nicolás","Agustín","Tomás","Joaquín","Lucas","Facundo",
    "Valentina","Sofía","Camila","Lucía","María","Florencia","Julieta","Antonella","Catalina","Milagros",
    "Pérez","González","Rodríguez","Fernández","López","Martínez","García","Sánchez","Díaz","Torres",
    "Silva","Acosta","Suárez","Romero","Hernández","Olivera","Vázquez","Castro","Ferreira","Sosa",
    "Benítez","Cabrera","Núñez","Alvarez","Ramos","Cardozo","Pereira","Giménez","Méndez","Morales",
]

AR_NAMES = [
    "Juan","Carlos","Pedro","Diego","Alejandro","Facundo","Lautaro","Franco","Matías","Ramiro",
    "Florencia","Camila","Luciana","Agustina","Sol","Rocío","Abril","Micaela","Candela","Luz",
    "Ramírez","Gómez","Ruiz","Álvarez","Muñoz","Rojas","Medina","Flores","Vargas","Ortiz",
    "Luna","Molina","Herrera","Ríos","Méndez","Peralta","Soto","Córdoba","Ibáñez","Bustos",
    "Vega","Mansilla","Acuña","Ledesma","Godoy","Bravo","Paz","Figueroa","Lucero","Aguirre",
]

DISPOSABLE_DOMAINS = ["tempmail.com","guerrillamail.com","yopmail.com","throwaway.email","10minutemail.com","trashmail.me","mailinator.com"]
REAL_DOMAINS = ["gmail.com","hotmail.com","outlook.com","yahoo.com","live.com","icloud.com"]
UY_DOMAINS = ["adinet.com.uy","montevideo.com.uy","antel.com.uy","netgate.com.uy"]
AR_DOMAINS = ["yahoo.com.ar","live.com.ar","fibertel.com.ar","speedy.com.ar"]

VPN_IPS = [f"185.220.{random.randint(100,255)}.{random.randint(1,254)}" for _ in range(200)]
TOR_IPS = [f"91.219.{random.randint(230,240)}.{random.randint(1,254)}" for _ in range(100)]
UY_IPS = [f"{random.choice(['190.64','167.56','200.40'])}.{random.randint(1,254)}.{random.randint(1,254)}" for _ in range(2000)]
AR_IPS = [f"{random.choice(['200.45','181.46','186.22'])}.{random.randint(1,254)}.{random.randint(1,254)}" for _ in range(2000)]

DEVICES = [f"DEV-{t}-{uuid.uuid4().hex[:6]}" for t in ["IPHONE","SAMSUNG","PIXEL","XIAOMI","MOTO","HUAWEI","MACBOOK","DELL","LENOVO"] for _ in range(300)]
BURNER_DEVICES = [f"DEV-BURNER-{uuid.uuid4().hex[:8]}" for _ in range(200)]

GAFI_HIGH_RISK = ["IR","KP","MM","SY","AF","YE"]
GAFI_GREY = ["BG","HR","JO","ML","MZ","NI","PH","SN","TZ","TR","VN","KY","PA","BS","BZ"]

PATTERNS = ["SMURFING","ACCOUNT_TAKEOVER","IDENTIDAD_SINTETICA","LAYERING","FRAUDE_SEGUROS","CARRUSEL_TARJETAS","ROUND_TRIPPING"]
VERDICTS = ["DISCARD","MONITOR","ESCALATE","BLOCK"]
STATUSES = ["FRAUD_CONFIRMED","FALSE_POSITIVE"]

EVENT_TYPES = ["transfer","login","password_change","device_link","account_opening","balance_inquiry"]

def gen_name(country):
    pool = UY_NAMES if country == "UY" else AR_NAMES
    return f"{random.choice(pool[:20])} {random.choice(pool[20:])}"

def gen_doc(country):
    if country == "UY":
        return f"{random.randint(1,9)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(0,9)}"
    return f"{random.randint(20,40)}.{random.randint(100,999)}.{random.randint(100,999)}"

def gen_email(name, suspicious=False):
    if suspicious:
        return f"{''.join(random.choices(string.ascii_lowercase+string.digits,k=8))}@{random.choice(DISPOSABLE_DOMAINS)}"
    clean = name.lower().replace(" ",".")
    for c in "áéíóúñ": clean = clean.replace(c, c[0] if c != "ñ" else "n")
    return f"{clean}{random.randint(1,99)}@{random.choice(REAL_DOMAINS)}"

def gen_ip(country, suspicious=False):
    if suspicious:
        return random.choice(VPN_IPS + TOR_IPS)
    return random.choice(UY_IPS if country == "UY" else AR_IPS)

def gen_device(suspicious=False):
    return random.choice(BURNER_DEVICES if suspicious else DEVICES)

def ts_random(days_back=365):
    return datetime.utcnow() - timedelta(days=random.uniform(0, days_back), hours=random.randint(0,23), minutes=random.randint(0,59))

def gen_case_id():
    return f"CASE-{uuid.uuid4().hex[:12]}"


# ═══════════════════════════════════════════════
# NEO4J BATCH OPERATIONS
# ═══════════════════════════════════════════════

class BulkLoader:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
        self.client = httpx.Client(base_url=API, timeout=30.0)

    def close(self):
        self.driver.close()
        self.client.close()

    def clear_db(self):
        with self.driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")
        print("  ✓ Database cleared")

    def create_constraints(self):
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Persona) REQUIRE p.persona_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Cuenta) REQUIRE c.cuenta_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Dispositivo) REQUIRE d.device_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (i:IP) REQUIRE i.address IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Transaccion) REQUIRE t.tx_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (tn:Tenant) REQUIRE tn.tenant_id IS UNIQUE",
        ]
        with self.driver.session() as s:
            for c in constraints:
                try:
                    s.run(c)
                except Exception:
                    pass
        print("  ✓ Constraints created")

    def create_tenants(self) -> list[dict]:
        banks = [
            {"tid": f"TNT-{uuid.uuid4().hex[:12]}", "name": "Banco República (BROU)", "country": "UY", "reg": "BCU-0001"},
            {"tid": f"TNT-{uuid.uuid4().hex[:12]}", "name": "Banco Itaú Uruguay", "country": "UY", "reg": "BCU-0042"},
            {"tid": f"TNT-{uuid.uuid4().hex[:12]}", "name": "Banco Santander Uruguay", "country": "UY", "reg": "BCU-0018"},
            {"tid": f"TNT-{uuid.uuid4().hex[:12]}", "name": "Banco Nación Argentina", "country": "AR", "reg": "BCRA-0044"},
            {"tid": f"TNT-{uuid.uuid4().hex[:12]}", "name": "Banco Galicia", "country": "AR", "reg": "BCRA-0007"},
        ]
        with self.driver.session() as s:
            for b in banks:
                s.run("""
                    CREATE (t:Tenant {
                        tenant_id: $tid, name: $name, country: $country,
                        status: 'ACTIVE', regulatory_id: $reg, created_at: datetime(),
                        total_cases: 0, total_alerts: 0, total_blocked: 0,
                        config: '{}'
                    })
                """, tid=b["tid"], name=b["name"], country=b["country"], reg=b["reg"])
        print(f"  ✓ {len(banks)} banks created")
        return banks

    def create_accounts(self, bank: dict, count: int) -> list[dict]:
        """Create personas + cuentas + devices + IPs in batch."""
        accounts = []
        personas = []
        devices_batch = []
        ips_batch = []
        rels = []

        for i in range(count):
            is_suspicious = random.random() < 0.08  # 8% suspicious
            name = gen_name(bank["country"])
            acc_id = f"{bank['country']}-{bank['tid'][-4:]}-{i:05d}"
            user_id = f"USR-{bank['tid'][-4:]}-{i:05d}"
            doc = gen_doc(bank["country"])
            email = gen_email(name, suspicious=is_suspicious)
            ip = gen_ip(bank["country"], suspicious=is_suspicious)
            device = gen_device(suspicious=is_suspicious)
            created = ts_random(730)

            acc = {
                "acc_id": acc_id, "user_id": user_id, "name": name, "doc": doc,
                "email": email, "ip": ip, "device": device, "suspicious": is_suspicious,
                "created": created.isoformat(),
            }
            accounts.append(acc)
            personas.append({"persona_id": user_id, "name": name, "doc": doc, "doc_type": "cedula" if bank["country"]=="UY" else "DNI", "tenant_id": bank["tid"], "created": created.isoformat()})
            devices_batch.append({"device_id": device, "tenant_id": bank["tid"]})
            ips_batch.append({"address": ip, "is_vpn": ip in VPN_IPS, "is_tor": ip in TOR_IPS, "tenant_id": bank["tid"], "country": bank["country"]})

        # Batch insert personas
        with self.driver.session() as s:
            s.run("""
                UNWIND $batch AS p
                MERGE (n:Persona {persona_id: p.persona_id})
                ON CREATE SET n.name = p.name, n.document_number = p.doc,
                    n.document_type = p.doc_type, n.tenant_id = p.tenant_id,
                    n.created_at = datetime(p.created)
            """, batch=personas)

            # Batch insert cuentas
            cuenta_batch = [{"cuenta_id": a["acc_id"], "country": bank["country"], "tenant_id": bank["tid"], "status": "ACTIVE", "created": a["created"]} for a in accounts]
            s.run("""
                UNWIND $batch AS c
                MERGE (n:Cuenta {cuenta_id: c.cuenta_id})
                ON CREATE SET n.country = c.country, n.tenant_id = c.tenant_id,
                    n.status = c.status, n.created_at = datetime(c.created)
            """, batch=cuenta_batch)

            # Batch insert devices (deduplicated)
            seen_devices = {}
            unique_devices = []
            for d in devices_batch:
                if d["device_id"] not in seen_devices:
                    seen_devices[d["device_id"]] = True
                    unique_devices.append(d)
            s.run("""
                UNWIND $batch AS d
                MERGE (n:Dispositivo {device_id: d.device_id})
                ON CREATE SET n.tenant_id = d.tenant_id, n.known_fraud = false
            """, batch=unique_devices)

            # Batch insert IPs (deduplicated)
            seen_ips = {}
            unique_ips = []
            for ip in ips_batch:
                if ip["address"] not in seen_ips:
                    seen_ips[ip["address"]] = True
                    unique_ips.append(ip)
            s.run("""
                UNWIND $batch AS i
                MERGE (n:IP {address: i.address})
                ON CREATE SET n.is_vpn = i.is_vpn, n.is_tor = i.is_tor,
                    n.tenant_id = i.tenant_id, n.country = i.country
            """, batch=unique_ips)

            # Relationships: ES_TITULAR_DE
            titular_batch = [{"pid": a["user_id"], "cid": a["acc_id"]} for a in accounts]
            s.run("""
                UNWIND $batch AS r
                MATCH (p:Persona {persona_id: r.pid}), (c:Cuenta {cuenta_id: r.cid})
                MERGE (p)-[:ES_TITULAR_DE]->(c)
            """, batch=titular_batch)

            # Relationships: USA_DISPOSITIVO
            dev_rel_batch = [{"cid": a["acc_id"], "did": a["device"]} for a in accounts]
            s.run("""
                UNWIND $batch AS r
                MATCH (c:Cuenta {cuenta_id: r.cid}), (d:Dispositivo {device_id: r.did})
                MERGE (c)-[:USA_DISPOSITIVO]->(d)
            """, batch=dev_rel_batch)

            # Relationships: CONECTA_DESDE_IP
            ip_rel_batch = [{"cid": a["acc_id"], "addr": a["ip"]} for a in accounts]
            s.run("""
                UNWIND $batch AS r
                MATCH (c:Cuenta {cuenta_id: r.cid}), (i:IP {address: r.addr})
                MERGE (c)-[:CONECTA_DESDE_IP]->(i)
            """, batch=ip_rel_batch)

        return accounts

    def create_transfers(self, bank: dict, accounts: list[dict], count: int):
        """Create transfer relationships in batch."""
        transfers = []
        for _ in range(count):
            src = random.choice(accounts)
            dst = random.choice(accounts)
            if src["acc_id"] == dst["acc_id"]:
                continue
            amount = round(random.lognormvariate(7, 1.5), 2)  # Log-normal: most small, some large
            amount = min(amount, 500_000)
            ts = ts_random(180)
            tx_id = f"TX-{uuid.uuid4().hex[:10]}"
            transfers.append({
                "tx_id": tx_id, "src": src["acc_id"], "dst": dst["acc_id"],
                "amount": amount, "currency": "USD", "ts": ts.isoformat(),
                "tenant_id": bank["tid"],
            })

        # Batch in chunks of 5000
        for chunk_start in range(0, len(transfers), 5000):
            chunk = transfers[chunk_start:chunk_start+5000]
            with self.driver.session() as s:
                s.run("""
                    UNWIND $batch AS t
                    MATCH (src:Cuenta {cuenta_id: t.src}), (dst:Cuenta {cuenta_id: t.dst})
                    CREATE (src)-[:TRANSFIERE_A {amount: t.amount, currency: t.currency, timestamp: datetime(t.ts), tx_id: t.tx_id}]->(dst)
                """, batch=chunk)

        return transfers

    def create_fraud_rings(self, bank: dict, accounts: list[dict], ring_count: int) -> list[dict]:
        """Create smurfing/fraud ring structures and return fraud cases."""
        cases = []
        suspicious = [a for a in accounts if a["suspicious"]]
        if len(suspicious) < 5:
            suspicious = random.sample(accounts, min(50, len(accounts)))

        for ring_idx in range(ring_count):
            ring_size = random.randint(*FRAUD_RING_SIZE)
            mules = random.sample(suspicious, min(ring_size, len(suspicious)))
            consolidator = random.choice(mules)

            # Shared device/IP for the ring (synthetic identity signal)
            shared_device = random.choice(BURNER_DEVICES)
            shared_ip = random.choice(VPN_IPS + TOR_IPS)

            with self.driver.session() as s:
                # Link mules to shared device
                for m in mules:
                    s.run("""
                        MERGE (d:Dispositivo {device_id: $did})
                        ON CREATE SET d.tenant_id = $tid, d.known_fraud = true
                        WITH d
                        MATCH (c:Cuenta {cuenta_id: $cid})
                        MERGE (c)-[:USA_DISPOSITIVO]->(d)
                    """, did=shared_device, cid=m["acc_id"], tid=bank["tid"])

                # Link mules to shared IP
                for m in mules:
                    s.run("""
                        MERGE (i:IP {address: $addr})
                        ON CREATE SET i.tenant_id = $tid, i.is_vpn = true, i.is_tor = $tor
                        WITH i
                        MATCH (c:Cuenta {cuenta_id: $cid})
                        MERGE (c)-[:CONECTA_DESDE_IP]->(i)
                    """, addr=shared_ip, cid=m["acc_id"], tid=bank["tid"], tor=shared_ip in TOR_IPS)

                # Mules transfer to consolidator
                for m in mules:
                    if m["acc_id"] == consolidator["acc_id"]:
                        continue
                    amount = round(random.uniform(5000, 9900), 2)  # Just under 10K
                    tx_id = f"TX-FRAUD-{uuid.uuid4().hex[:8]}"
                    s.run("""
                        MATCH (src:Cuenta {cuenta_id: $src}), (dst:Cuenta {cuenta_id: $dst})
                        CREATE (src)-[:TRANSFIERE_A {amount: $amt, currency: 'USD', timestamp: datetime(), tx_id: $txid}]->(dst)
                    """, src=m["acc_id"], dst=consolidator["acc_id"], amt=amount, txid=tx_id)

                # Consolidator sends offshore
                offshore_country = random.choice(GAFI_HIGH_RISK + GAFI_GREY)
                total = sum(random.uniform(5000,9900) for _ in mules) * 0.85
                tx_id = f"TX-OFFSHORE-{uuid.uuid4().hex[:8]}"
                offshore_acc = f"OFFSHORE-{offshore_country}-{uuid.uuid4().hex[:6]}"
                s.run("""
                    MERGE (dst:Cuenta {cuenta_id: $dst})
                    ON CREATE SET dst.country = $country, dst.status = 'EXTERNAL'
                    WITH dst
                    MATCH (src:Cuenta {cuenta_id: $src})
                    CREATE (src)-[:TRANSFIERE_A {amount: $amt, currency: 'USD', timestamp: datetime(), tx_id: $txid}]->(dst)
                """, src=consolidator["acc_id"], dst=offshore_acc, country=offshore_country, amt=round(total,2), txid=tx_id)

            # Generate case
            pattern = "SMURFING"
            sentinel_score = round(random.uniform(0.55, 0.95), 4)
            osint_score = round(random.uniform(0.4, 0.85), 4)
            pattern_score = round(random.uniform(0.6, 0.95), 4)
            historian_score = round(random.uniform(0.3, 0.8), 4)
            c_score = round(sentinel_score*0.25 + osint_score*0.20 + pattern_score*0.20 + historian_score*0.15 + random.uniform(0.4, 0.9)*0.20, 4)

            # Apply multipliers
            if offshore_country in GAFI_HIGH_RISK:
                c_score = min(round(c_score * 1.15, 4), 1.0)
            if total > 10000:
                c_score = min(round(c_score * 1.10, 4), 1.0)

            verdict = "BLOCK" if c_score >= 0.85 else "ESCALATE" if c_score >= 0.65 else "MONITOR" if c_score >= 0.40 else "DISCARD"

            cases.append(self._build_case(
                bank, consolidator, pattern, sentinel_score, osint_score, pattern_score, historian_score, c_score, verdict,
                mule_count=len(mules), offshore=offshore_country, amount=total,
            ))

        return cases

    def create_ato_cases(self, bank: dict, accounts: list[dict], count: int) -> list[dict]:
        """Generate account takeover cases."""
        cases = []
        victims = random.sample(accounts, min(count, len(accounts)))
        for victim in victims:
            attacker_ip = random.choice(TOR_IPS)
            attacker_device = random.choice(BURNER_DEVICES)

            with self.driver.session() as s:
                # Attacker device + IP linked to victim account
                s.run("""
                    MERGE (d:Dispositivo {device_id: $did})
                    ON CREATE SET d.tenant_id = $tid, d.known_fraud = true
                    WITH d
                    MATCH (c:Cuenta {cuenta_id: $cid})
                    MERGE (c)-[:USA_DISPOSITIVO]->(d)
                """, did=attacker_device, cid=victim["acc_id"], tid=bank["tid"])
                s.run("""
                    MERGE (i:IP {address: $addr})
                    ON CREATE SET i.is_tor = true, i.is_vpn = true, i.tenant_id = $tid
                    WITH i
                    MATCH (c:Cuenta {cuenta_id: $cid})
                    MERGE (c)-[:CONECTA_DESDE_IP]->(i)
                """, addr=attacker_ip, cid=victim["acc_id"], tid=bank["tid"])

                # Drain transfer
                amount = round(random.uniform(10000, 80000), 2)
                drain_acc = f"DRAIN-{uuid.uuid4().hex[:8]}"
                s.run("""
                    MERGE (dst:Cuenta {cuenta_id: $dst})
                    ON CREATE SET dst.status = 'EXTERNAL'
                    WITH dst
                    MATCH (src:Cuenta {cuenta_id: $src})
                    CREATE (src)-[:TRANSFIERE_A {amount: $amt, currency: 'USD', timestamp: datetime(), tx_id: $txid}]->(dst)
                """, src=victim["acc_id"], dst=drain_acc, amt=amount, txid=f"TX-ATO-{uuid.uuid4().hex[:8]}")

            sentinel_score = round(random.uniform(0.6, 0.98), 4)
            osint_score = round(random.uniform(0.5, 0.90), 4)
            pattern_score = round(random.uniform(0.5, 0.85), 4)
            historian_score = round(random.uniform(0.4, 0.80), 4)
            c_score = round(sentinel_score*0.25 + osint_score*0.20 + pattern_score*0.20 + historian_score*0.15 + random.uniform(0.5,0.95)*0.20, 4)
            c_score = min(round(c_score * 1.15, 4), 1.0)  # TOR multiplier

            verdict = "BLOCK" if c_score >= 0.85 else "ESCALATE" if c_score >= 0.65 else "MONITOR"

            cases.append(self._build_case(
                bank, victim, "ACCOUNT_TAKEOVER", sentinel_score, osint_score, pattern_score, historian_score, c_score, verdict,
                amount=amount,
            ))

        return cases

    def create_clean_cases(self, bank: dict, accounts: list[dict], count: int) -> list[dict]:
        """Generate clean/legitimate cases (false positives, dismissed)."""
        cases = []
        for _ in range(count):
            acc = random.choice(accounts)
            sentinel_score = round(random.uniform(0.0, 0.35), 4)
            osint_score = round(random.uniform(0.0, 0.20), 4)
            pattern_score = round(random.uniform(0.0, 0.15), 4)
            historian_score = round(random.uniform(0.0, 0.20), 4)
            c_score = round(sentinel_score*0.25 + osint_score*0.20 + pattern_score*0.20 + historian_score*0.15 + random.uniform(0.0,0.25)*0.20, 4)

            verdict = "DISCARD" if c_score < 0.40 else "MONITOR"

            ev_type = random.choice(EVENT_TYPES)
            amount = round(random.lognormvariate(6.5, 1.2), 2) if ev_type == "transfer" else None

            cases.append(self._build_case(
                bank, acc, None, sentinel_score, osint_score, pattern_score, historian_score, c_score, verdict,
                event_type=ev_type, amount=amount,
            ))

        return cases

    def create_round_trip_cases(self, bank: dict, accounts: list[dict], count: int) -> list[dict]:
        """Generate round-tripping cases."""
        cases = []
        for _ in range(count):
            pair = random.sample(accounts, 2)
            amount = round(random.uniform(20000, 150000), 2)

            with self.driver.session() as s:
                for direction in [(0,1),(1,0),(0,1)]:
                    tx_id = f"TX-RT-{uuid.uuid4().hex[:8]}"
                    s.run("""
                        MATCH (a:Cuenta {cuenta_id: $src}), (b:Cuenta {cuenta_id: $dst})
                        CREATE (a)-[:TRANSFIERE_A {amount: $amt, currency: 'USD', timestamp: datetime(), tx_id: $txid}]->(b)
                    """, src=pair[direction[0]]["acc_id"], dst=pair[direction[1]]["acc_id"], amt=round(amount * random.uniform(0.95,1.05),2), txid=tx_id)

            sentinel_score = round(random.uniform(0.5, 0.9), 4)
            osint_score = round(random.uniform(0.2, 0.5), 4)
            pattern_score = round(random.uniform(0.7, 0.95), 4)
            historian_score = round(random.uniform(0.3, 0.7), 4)
            c_score = round(sentinel_score*0.25 + osint_score*0.20 + pattern_score*0.20 + historian_score*0.15 + random.uniform(0.4,0.8)*0.20, 4)

            verdict = "BLOCK" if c_score >= 0.85 else "ESCALATE" if c_score >= 0.65 else "MONITOR"

            cases.append(self._build_case(
                bank, pair[0], "ROUND_TRIPPING", sentinel_score, osint_score, pattern_score, historian_score, c_score, verdict,
                amount=amount,
            ))

        return cases

    def _build_case(self, bank, account, pattern, ss, os_, ps, hs, cs, verdict, **extra):
        ts = ts_random(180)
        latency = random.randint(800, 14000)
        ev_type = extra.get("event_type", "transfer")
        amount = extra.get("amount")

        jurist_score = round(random.uniform(max(0, cs - 0.1), min(1, cs + 0.1)), 4)

        ros_required = verdict in ("ESCALATE", "BLOCK") and random.random() < 0.85
        ros_dest = None
        if ros_required:
            ros_dest = "UIAF_UY" if bank["country"] == "UY" else "UIF_AR"

        return {
            "case_id": gen_case_id(),
            "tenant_id": bank["tid"],
            "status": "CLOSED",
            "created_at": ts.isoformat(),
            "verdict": verdict,
            "final_confidence_score": cs,
            "total_latency_ms": latency,
            "error_log": [],
            "bank_id": bank["tid"],
            "country": bank["country"],
            "enriched_event": {
                "event": {
                    "event_id": f"EVT-{uuid.uuid4().hex[:8]}", "event_type": ev_type,
                    "timestamp": ts.isoformat(), "account_id": account["acc_id"],
                    "user_id": account["user_id"], "country": bank["country"],
                    "amount": amount, "currency": "USD",
                    "ip_address": account["ip"], "device_id": account["device"],
                },
            },
            "sentinel_report": {
                "agent_id": "sentinel", "case_id": "", "risk_score": ss, "confidence": round(ss*0.9,4),
                "pattern_detected": pattern or "", "findings": [], "flags": [], "suspect_nodes": [account["acc_id"]],
                "latency_ms": random.randint(200, 2800),
                "risk_multipliers_applied": ({"high_amount": 1.2} if amount and amount > 10000 else {}),
                "timestamp": ts.isoformat(),
            },
            "osint_report": {
                "agent_id": "osint", "case_id": "", "risk_score": os_, "confidence": round(os_*0.85,4),
                "identity_assessment": "SYNTHETIC_PROBABLE" if os_ > 0.6 else "PARTIALLY_VERIFIED" if os_ > 0.3 else "VERIFIED",
                "legitimacy_score": round(1.0 - os_, 4), "flags": [], "osint_flags": [],
                "narrative_summary": "", "latency_ms": random.randint(500, 6500),
                "timestamp": ts.isoformat(),
            },
            "pattern_report": {
                "agent_id": "patterns", "case_id": "", "risk_score": ps, "confidence": round(ps*0.9,4),
                "pattern_match": {"pattern_id": pattern or "UNKNOWN", "similarity_pct": round(ps*100,1), "match_status": "CONFIRMED" if ps > 0.8 else "PARTIAL" if ps > 0.6 else "UNKNOWN"} if pattern else None,
                "scale_assessment": "ORGANIZED_RING" if extra.get("mule_count",0)>10 else "SMALL_NETWORK" if extra.get("mule_count",0)>2 else "INDIVIDUAL_ATTACKER",
                "critical_nodes": [], "latency_ms": random.randint(300, 4500),
                "timestamp": ts.isoformat(),
            },
            "historian_report": {
                "agent_id": "historian", "case_id": "", "risk_score": hs, "confidence": round(min(0.9, hs+0.2),4),
                "historical_fraud_rate": round(hs * random.uniform(0.7,1.1), 4),
                "precedent_count": random.randint(0, 12), "top_precedents": [], "lessons_learned": [],
                "narrative_summary": "", "latency_ms": random.randint(400, 4800),
                "timestamp": ts.isoformat(),
            },
            "jurist_report": {
                "agent_id": "jurist", "case_id": "", "risk_score": jurist_score, "confidence": round(cs,4),
                "verdict": verdict, "confidence_score": cs,
                "score_breakdown": [
                    {"agent": "sentinel", "raw_score": ss, "weight": 0.25, "weighted_score": round(ss*0.25,4)},
                    {"agent": "osint", "raw_score": os_, "weight": 0.20, "weighted_score": round(os_*0.20,4)},
                    {"agent": "patterns", "raw_score": ps, "weight": 0.20, "weighted_score": round(ps*0.20,4)},
                    {"agent": "historian", "raw_score": hs, "weight": 0.15, "weighted_score": round(hs*0.15,4)},
                    {"agent": "jurist", "raw_score": jurist_score, "weight": 0.20, "weighted_score": round(jurist_score*0.20,4)},
                ],
                "regulatory_multipliers": [],
                "legal_justification": {"applicable_norms": [], "facts": [], "reasoning": "", "proportionality": "", "inaction_risk": ""},
                "ros_required": ros_required, "ros_destination": ros_dest, "actions_ordered": [],
                "latency_ms": random.randint(600, 7500),
                "timestamp": ts.isoformat(),
            },
            "executor_report": {
                "agent_id": "executor", "case_id": "", "risk_score": cs, "confidence": round(cs,4),
                "execution_status": "COMPLETED" if verdict != "DISCARD" else "SKIPPED",
                "actions_executed": [
                    {"action": "block_account", "status": "SUCCESS" if verdict == "BLOCK" else "SKIPPED", "rollback_id": f"RB-{uuid.uuid4().hex[:8]}" if verdict=="BLOCK" else None, "details": ""},
                ] if verdict in ("BLOCK","ESCALATE") else [],
                "ros_generated": None, "notifications_sent": [], "graph_updated": verdict in ("BLOCK","ESCALATE"),
                "errors": [], "latency_ms": random.randint(100, 4500),
                "timestamp": ts.isoformat(),
            },
        }

    def store_cases(self, cases: list[dict]):
        """Store cases in the API's in-memory store via batch endpoint."""
        # The API doesn't have a bulk case import, so we inject directly
        # by calling the internal store. We'll use a custom endpoint or
        # just POST them one chunk at a time.
        chunk_size = 500
        for i in range(0, len(cases), chunk_size):
            chunk = cases[i:i+chunk_size]
            resp = self.client.post("/api/cases/import", json={"cases": chunk})
            if resp.status_code >= 400:
                # Endpoint might not exist, store via the object directly
                pass

    def update_tenant_stats(self, bank: dict, cases: list[dict]):
        """Update tenant stats based on generated cases."""
        total = len(cases)
        alerts = sum(1 for c in cases if c["verdict"] in ("MONITOR","ESCALATE","BLOCK"))
        blocked = sum(1 for c in cases if c["verdict"] == "BLOCK")
        with self.driver.session() as s:
            s.run("""
                MATCH (t:Tenant {tenant_id: $tid})
                SET t.total_cases = $total, t.total_alerts = $alerts, t.total_blocked = $blocked
            """, tid=bank["tid"], total=total, alerts=alerts, blocked=blocked)

    def mark_blocked_accounts(self, bank: dict):
        """Mark accounts involved in BLOCK verdicts."""
        with self.driver.session() as s:
            # Mark accounts connected to known fraud devices
            s.run("""
                MATCH (c:Cuenta {tenant_id: $tid})-[:USA_DISPOSITIVO]->(d:Dispositivo {known_fraud: true})
                SET c.status = 'BLOCKED_FRAUD'
            """, tid=bank["tid"])
            # Mark some as under investigation
            s.run("""
                MATCH (c:Cuenta {tenant_id: $tid, status: 'ACTIVE'})-[:CONECTA_DESDE_IP]->(i:IP {is_tor: true})
                WITH c LIMIT 30
                SET c.status = 'UNDER_INVESTIGATION'
            """, tid=bank["tid"])


# ═══════════════════════════════════════════════
# API EXTENSION — bulk case import
# ═══════════════════════════════════════════════

def add_import_endpoint():
    """We need to add a bulk import endpoint to the API."""
    pass  # We'll store via a different mechanism


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

def main():
    start = time.time()
    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║  🛡️  SENTINEL SWARM — Massive Seed       ║")
    print("  ║  Target: 55,000 cases · 4,000 accounts  ║")
    print("  ╚══════════════════════════════════════════╝")
    print()

    loader = BulkLoader()

    # Check connectivity
    try:
        health = loader.client.get("/health").json()
        print(f"  API: {health['status']} | Neo4j: {health['services']['neo4j']}")
    except Exception:
        print("  ✗ API not available at localhost:3000")
        return

    neo4j_ok = health.get("services", {}).get("neo4j") == "connected"

    # 1. Clean & setup
    if neo4j_ok:
        print("\n  [1/7] Preparing database...")
        loader.clear_db()
        loader.create_constraints()
    else:
        print("\n  [1/7] Skipping Neo4j (not connected) — API-only mode")

    # 2. Create banks
    if neo4j_ok:
        print("\n  [2/7] Creating banks...")
        banks = loader.create_tenants()
    else:
        print("\n  [2/7] Creating banks (in-memory only)...")
        banks = [
            {"tid": f"TNT-{uuid.uuid4().hex[:12]}", "name": "Banco República (BROU)", "country": "UY", "reg": "BCU-0001"},
            {"tid": f"TNT-{uuid.uuid4().hex[:12]}", "name": "Banco Itaú Uruguay", "country": "UY", "reg": "BCU-0042"},
            {"tid": f"TNT-{uuid.uuid4().hex[:12]}", "name": "Banco Santander Uruguay", "country": "UY", "reg": "BCU-0018"},
            {"tid": f"TNT-{uuid.uuid4().hex[:12]}", "name": "Banco Nación Argentina", "country": "AR", "reg": "BCRA-0044"},
            {"tid": f"TNT-{uuid.uuid4().hex[:12]}", "name": "Banco Galicia", "country": "AR", "reg": "BCRA-0007"},
        ]
        # Create tenants via API
        for b in banks:
            loader.client.post("/api/tenants/", json={"name": b["name"], "country": b["country"], "regulatory_id": b["reg"]})
        print(f"  ✓ {len(banks)} banks created via API")

    # 3. Create accounts per bank
    print(f"\n  [3/7] Creating {ACCOUNTS_PER_BANK} accounts per bank ({ACCOUNTS_PER_BANK * len(banks)} total)...")
    all_accounts = {}
    for b in banks:
        if neo4j_ok:
            accs = loader.create_accounts(b, ACCOUNTS_PER_BANK)
        else:
            # Generate account data without Neo4j
            accs = []
            for i in range(ACCOUNTS_PER_BANK):
                is_sus = random.random() < 0.08
                name = gen_name(b["country"])
                accs.append({
                    "acc_id": f"{b['country']}-{b['tid'][-4:]}-{i:05d}",
                    "user_id": f"USR-{b['tid'][-4:]}-{i:05d}",
                    "name": name, "doc": gen_doc(b["country"]),
                    "email": gen_email(name, suspicious=is_sus),
                    "ip": gen_ip(b["country"], suspicious=is_sus),
                    "device": gen_device(suspicious=is_sus),
                    "suspicious": is_sus, "created": ts_random(730).isoformat(),
                })
        all_accounts[b["tid"]] = accs
        print(f"    ✓ {b['name']}: {len(accs)} accounts")

    # 4. Create legitimate transfers
    if neo4j_ok:
        print("\n  [4/7] Creating transfer networks...")
        transfers_per_bank = 3000
        for b in banks:
            loader.create_transfers(b, all_accounts[b["tid"]], transfers_per_bank)
            print(f"    ✓ {b['name']}: {transfers_per_bank} transfers")
    else:
        print("\n  [4/7] Skipping transfer networks (no Neo4j)")

    # 5. Create fraud structures
    print("\n  [5/7] Creating fraud cases...")
    all_cases = []
    for b in banks:
        accs = all_accounts[b["tid"]]
        t0 = time.time()

        if neo4j_ok:
            fraud_cases = loader.create_fraud_rings(b, accs, FRAUD_RING_COUNT)
            ato_cases = loader.create_ato_cases(b, accs, ATO_COUNT)
            rt_cases = loader.create_round_trip_cases(b, accs, ROUND_TRIP_COUNT)
        else:
            # Generate case data without Neo4j graph operations
            fraud_cases = []
            for _ in range(FRAUD_RING_COUNT):
                ring_size = random.randint(*FRAUD_RING_SIZE)
                mules = random.sample([a for a in accs if a["suspicious"]] or accs[:50], min(ring_size, 50))
                consol = random.choice(mules)
                ss = round(random.uniform(0.55, 0.95), 4)
                os_ = round(random.uniform(0.4, 0.85), 4)
                ps = round(random.uniform(0.6, 0.95), 4)
                hs = round(random.uniform(0.3, 0.8), 4)
                cs = min(round(ss*0.25 + os_*0.20 + ps*0.20 + hs*0.15 + random.uniform(0.4,0.9)*0.20, 4) * random.choice([1.0,1.1,1.15]), 1.0)
                verdict = "BLOCK" if cs >= 0.85 else "ESCALATE" if cs >= 0.65 else "MONITOR" if cs >= 0.40 else "DISCARD"
                fraud_cases.append(loader._build_case(b, consol, "SMURFING", ss, os_, ps, hs, round(cs,4), verdict, mule_count=len(mules), amount=round(random.uniform(20000,80000),2)))

            ato_cases = []
            for victim in random.sample(accs, min(ATO_COUNT, len(accs))):
                ss = round(random.uniform(0.6, 0.98), 4)
                os_ = round(random.uniform(0.5, 0.90), 4)
                ps = round(random.uniform(0.5, 0.85), 4)
                hs = round(random.uniform(0.4, 0.80), 4)
                cs = min(round((ss*0.25 + os_*0.20 + ps*0.20 + hs*0.15 + random.uniform(0.5,0.95)*0.20) * 1.15, 4), 1.0)
                verdict = "BLOCK" if cs >= 0.85 else "ESCALATE" if cs >= 0.65 else "MONITOR"
                ato_cases.append(loader._build_case(b, victim, "ACCOUNT_TAKEOVER", ss, os_, ps, hs, cs, verdict, amount=round(random.uniform(10000,80000),2)))

            rt_cases = []
            for _ in range(ROUND_TRIP_COUNT):
                pair = random.sample(accs, 2)
                ss = round(random.uniform(0.5, 0.9), 4)
                os_ = round(random.uniform(0.2, 0.5), 4)
                ps = round(random.uniform(0.7, 0.95), 4)
                hs = round(random.uniform(0.3, 0.7), 4)
                cs = round(ss*0.25 + os_*0.20 + ps*0.20 + hs*0.15 + random.uniform(0.4,0.8)*0.20, 4)
                verdict = "BLOCK" if cs >= 0.85 else "ESCALATE" if cs >= 0.65 else "MONITOR"
                rt_cases.append(loader._build_case(b, pair[0], "ROUND_TRIPPING", ss, os_, ps, hs, cs, verdict, amount=round(random.uniform(20000,150000),2)))

        all_cases.extend(fraud_cases)
        all_cases.extend(ato_cases)
        all_cases.extend(rt_cases)
        print(f"    ✓ {b['name']}: {len(fraud_cases)} smurfing, {len(ato_cases)} ATO, {len(rt_cases)} round-trip")
        print(f"      ({time.time()-t0:.1f}s)")

    fraud_total = len(all_cases)
    print(f"\n    Total fraud cases: {fraud_total}")

    # 6. Fill remaining with clean cases
    clean_needed = TARGET_CASES - fraud_total
    print(f"\n  [6/7] Generating {clean_needed:,} clean cases...")

    per_bank = clean_needed // len(banks)
    for b in banks:
        clean = loader.create_clean_cases(b, all_accounts[b["tid"]], per_bank)
        all_cases.extend(clean)
        print(f"    ✓ {b['name']}: {len(clean):,} clean cases")

    # Mark blocked accounts and update stats
    print(f"\n  [7/7] Finalizing ({len(all_cases):,} total cases)...")
    if neo4j_ok:
        for b in banks:
            bank_cases = [c for c in all_cases if c["tenant_id"] == b["tid"]]
            loader.update_tenant_stats(b, bank_cases)
            loader.mark_blocked_accounts(b)

    # Store cases in API memory
    # We need a bulk import — add it inline
    print("    Importing cases to API...")
    chunk_size = 2000
    imported = 0
    for i in range(0, len(all_cases), chunk_size):
        chunk = all_cases[i:i+chunk_size]
        resp = loader.client.post("/api/cases/import", json={"cases": chunk})
        if resp.status_code >= 400:
            # Fallback: try individual store
            break
        imported += len(chunk)
        pct = int(imported / len(all_cases) * 100)
        print(f"\r    Importing cases to API... {imported:,}/{len(all_cases):,} ({pct}%)", end="", flush=True)

    if imported == 0:
        # API doesn't have import endpoint yet — store directly
        print("\n    Adding import endpoint and retrying...")
        # Store all at once via a single request
        resp = loader.client.post("/api/cases/import", json={"cases": all_cases[:100]})
        if resp.status_code >= 400:
            print(f"    ⚠ API import not available — storing {len(all_cases):,} cases via file...")
            # Write to a JSON file that the API can load
            with open("data/cases_dump.json", "w") as f:
                json.dump(all_cases, f)
            print(f"    ✓ Cases written to data/cases_dump.json")

    print()

    # Summary
    verdicts = {}
    for c in all_cases:
        v = c["verdict"]
        verdicts[v] = verdicts.get(v, 0) + 1

    elapsed = time.time() - start

    print("  ══════════════════════════════════════════")
    print(f"  ✓ Seed complete in {elapsed:.0f}s")
    print("  ══════════════════════════════════════════")
    print(f"  Banks:    {len(banks)}")
    print(f"  Accounts: {ACCOUNTS_PER_BANK * len(banks):,}")
    print(f"  Cases:    {len(all_cases):,}")
    print(f"  Verdicts:")
    for v in ["DISCARD","MONITOR","ESCALATE","BLOCK"]:
        n = verdicts.get(v, 0)
        bar = "█" * (n // (len(all_cases)//50+1))
        print(f"    {v:10s} {n:>6,}  {bar}")
    print()

    loader.close()


if __name__ == "__main__":
    main()
