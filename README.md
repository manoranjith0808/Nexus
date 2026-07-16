# Sentinel Swarm

**Autonomous Risk Operating System (AROS) for real-time financial fraud detection.**

Sentinel Swarm is an open-source, AI-powered fraud detection platform designed for banks in Latin America. It combines graph-based analysis, multi-agent AI orchestration, and open banking data to detect, investigate, and act on financial fraud in real time.

> **This is a functional proof-of-concept / research project.** It demonstrates how modern AI agent architectures can be applied to financial crime detection. It is not production-ready and should not be used with real customer data without proper security hardening, compliance review, and regulatory approval.

---

## What it does

Sentinel Swarm processes banking events (transfers, logins, password changes, device links) through a pipeline of 6 specialized AI agents that collaborate to detect fraud patterns, assess risk, and recommend actions — all in under 15 seconds.

```
Banking Event → Enrichment → Graph Analysis → 6 AI Agents → Decision → Action
```

### The pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   Event (transfer, login, etc.)                             │
│     │                                                       │
│     ▼                                                       │
│   Enrichment (IP geolocation, device reputation, history)   │
│     │                                                       │
│     ▼                                                       │
│   Neo4j Graph (accounts, people, devices, IPs, txns)        │
│     │                                                       │
│     ▼                                                       │
│   Agent 1: EL CENTINELA ─────────────────────────────┐      │
│   Monitors graph topology for anomalies              │      │
│   If risk >= 0.3 → triggers investigation            │      │
│     │                                                │      │
│     ├──────────────┬──────────────┐                  │      │
│     ▼              ▼              ▼                  │      │
│   Agent 2        Agent 3        Agent 4              │      │
│   OSINT          PATTERNS       HISTORIAN            │      │
│   Identity       Attack         Historical           │      │
│   validation     classification precedents           │      │
│     │              │              │                   │      │
│     └──────────────┴──────────────┘                  │      │
│                    │                                  │      │
│                    ▼                                  │      │
│   Agent 5: EL JURISTA                                │      │
│   Weighs all evidence against regulatory framework   │      │
│   Calculates confidence score                        │      │
│   Issues verdict: DISCARD / MONITOR / ESCALATE / BLOCK      │
│     │                                                │      │
│     ▼                                                │      │
│   Agent 6: EL EJECUTOR                               │      │
│   Blocks accounts, cancels transactions              │      │
│   Generates regulatory reports (ROS/SAR)             │      │
│   Notifies compliance, updates graph                 │      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### The 6 agents

| # | Agent | Role | Model |
|---|-------|------|-------|
| 1 | **El Centinela** (The Sentinel) | Continuous graph monitoring. Detects ring attacks, smurfing networks, synthetic identities, velocity anomalies, bridge nodes, suspicious action chains, and proximity to blocked accounts. | Llama-3 70B |
| 2 | **El Investigador OSINT** (The Stalker) | External identity validation. Checks email age, phone portability, IP reputation, breach databases, and overall identity coherence. | GPT-4o |
| 3 | **El Arquitecto de Patrones** (Pattern Matcher) | Classifies attack type by comparing sub-graphs against a library of 7 known fraud topologies using structural similarity. | Llama-3 70B |
| 4 | **El Historiador Forense** (Memory Keeper) | Searches a RAG vector database of closed cases for similar precedents and calculates historical fraud rates. | Embeddings + Llama-3 70B |
| 5 | **El Jurista** (The Judge) | Evaluates all evidence against UY/AR regulatory frameworks. Calculates weighted confidence score with regulatory multipliers. Issues the final verdict. | Claude Opus |
| 6 | **El Ejecutor** (The Executor) | The only agent with write permissions. Blocks accounts, cancels transactions, generates ROS reports, notifies compliance, and updates the graph. | Llama-3 70B |

### Fraud patterns detected

- **Smurfing / Structuring** — breaking large amounts into smaller transfers to avoid reporting thresholds
- **Account Takeover** — device link → password change → drain transfer chain
- **Synthetic Identity** — fabricated identities sharing devices/IPs across multiple accounts
- **Layering** — cascading transfers through 4-8 layers to obscure fund origin
- **Round-Tripping** — circular transfers between related entities
- **Card Carousel** — coordinated card fraud across multiple accounts
- **Insurance Fraud** — bipartite graph patterns in claims

---

## Architecture

### Four layers

```
┌──────────────────────────────────────────────────┐
│  INGESTION          Apache Kafka                 │
│  Events from core banking → enrichment pipeline  │
├──────────────────────────────────────────────────┤
│  GRAPH              Neo4j + GDS                  │
│  Nodes: Person, Account, Device, IP, Transaction │
│  Algorithms: Louvain, PageRank, Betweenness,     │
│              Jaccard similarity                  │
├──────────────────────────────────────────────────┤
│  AI MULTI-MODEL                                  │
│  Llama-3 70B (local, PII-safe)                   │
│  GPT-4o (OSINT, NLP)                             │
│  Claude Opus (legal reasoning)                   │
│  Embeddings (RAG vector store)                   │
├──────────────────────────────────────────────────┤
│  ORCHESTRATION      LangGraph                    │
│  6 agents, conditional branching, timeouts       │
│  Full pipeline < 15 seconds                      │
└──────────────────────────────────────────────────┘
```

### Multi-tenant

Each bank gets isolated data (separated by `tenant_id` in the graph), but shares anonymized intelligence across tenants:
- Cross-bank IP/device correlations
- Shared fraud pattern signatures
- Anonymized topology features for model training

### Prometeo Open Banking integration

Connects to real bank accounts in LATAM via [Prometeo API](https://prometeoapi.com) to pull:
- Account balances and details
- Transaction history / movements
- Credit card data
- Transfer logs and lifecycle (preprocess, confirm, batch)

---

## Tech stack

| Component | Technology |
|-----------|-----------|
| Backend API | FastAPI (Python 3.12) |
| Agent orchestration | LangGraph |
| Graph database | Neo4j 5.x + Graph Data Science |
| Event streaming | Apache Kafka (KRaft mode) |
| Cache | Redis 7 |
| Vector store | ChromaDB |
| LLMs | OpenAI GPT-4o, Anthropic Claude, Llama-3 70B |
| Open banking | Prometeo API |
| Dashboard | Streamlit |
| Graph visualization | vis.js |
| Containerization | Docker Compose |

---

## Quick start

### Prerequisites

- Python 3.12+
- Docker Desktop
- API keys (optional for demo mode):
  - OpenAI (`OPENAI_API_KEY`)
  - Anthropic (`ANTHROPIC_API_KEY`)
  - Prometeo (`PROMETEO_API_KEY`) — free sandbox at [prometeoapi.com](https://prometeoapi.com)

### One command

```bash
git clone https://github.com/your-username/sentinel-swarm.git
cd sentinel-swarm
./start.sh
```

This will:
1. Check prerequisites (Python, Docker)
2. Start Docker Desktop if not running
3. Create a Python virtual environment and install dependencies
4. Start infrastructure (Neo4j, Kafka, Redis, ChromaDB)
5. Start the API server (port 3000)
6. Start the dashboard (port 8501)

### Manual setup

```bash
# 1. Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install streamlit plotly httpx

# 2. Copy environment file
cp .env.example .env
# Edit .env with your API keys

# 3. Start infrastructure
docker compose -f docker/docker-compose.yml up -d

# 4. Start API
uvicorn sentinel_swarm.api.app:app --host 0.0.0.0 --port 3000

# 5. Start dashboard (new terminal)
streamlit run dashboard.py --server.port 8501

# 6. Load test data (55,000 cases)
python seed_massive.py
```

### Access

| Service | URL |
|---------|-----|
| **Dashboard** | http://localhost:8501 |
| **API** | http://localhost:3000 |
| **API Docs (Swagger)** | http://localhost:3000/docs |
| **Neo4j Browser** | http://localhost:7474 |

---

## Loading test data

The seed script generates realistic test data. Works with or without Neo4j:

```bash
python seed_massive.py
```

This creates:
- **5 banks** (3 Uruguay, 2 Argentina)
- **4,000 accounts** with personas, devices, and IPs
- **55,000 cases** including:
  - 200 smurfing rings
  - 300 account takeovers
  - 150 round-tripping schemes
  - 54,350 legitimate transactions
- **650 active alerts** for analyst review
- Data persists to `data/cases_store.json` and survives API restarts

---

## API reference

### Alerts (analyst workflow)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/alerts/queue` | Prioritized alert queue with filters |
| `GET` | `/api/alerts/queue/stats` | Queue statistics (pending, critical, etc.) |
| `GET` | `/api/alerts/{case_id}` | Full alert detail with all agent reports |
| `POST` | `/api/alerts/{case_id}/decide` | Record decision: APPROVE / REJECT / ESCALATE |
| `POST` | `/api/alerts/{case_id}/assign` | Assign alert to an analyst |

### Cases

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/cases/` | List cases with filters (verdict, score, tenant) |
| `GET` | `/api/cases/{id}` | Full case detail |
| `GET` | `/api/cases/{id}/timeline` | Agent execution timeline |
| `GET` | `/api/cases/{id}/agents/{agent}` | Individual agent report |
| `GET` | `/api/cases/stats/summary` | Aggregate statistics |
| `POST` | `/api/cases/import` | Bulk import cases |

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/reports/{case_id}/narrative` | Auto-generated case narrative |
| `GET` | `/api/reports/{case_id}/ros` | Structured ROS/SAR report |
| `GET` | `/api/reports/{case_id}/ros/html` | Printable ROS (HTML, use browser Print → PDF) |

### Events

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/events/process` | Process event through 6-agent pipeline |
| `POST` | `/api/events/process/bulk` | Process multiple events |

### Graph exploration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/graph/{tid}/full` | Full graph for a tenant |
| `GET` | `/api/graph/{tid}/subgraph/{node}` | Neighborhood around a node |
| `GET` | `/api/graph/{tid}/contaminated` | Nodes connected to fraud (risk spread) |
| `GET` | `/api/graph/{tid}/transfers` | Transfer flow graph |
| `GET` | `/api/graph/{tid}/shared-resources` | Shared devices/IPs across accounts |
| `GET` | `/api/graph/{tid}/cycles` | Circular transfer detection |
| `GET` | `/api/graph/{tid}/communities` | Community detection |
| `POST` | `/api/graph/{tid}/query` | Raw Cypher query |
| `GET` | `/api/graph/cross-tenant/compare` | Cross-bank shared connections |

### Tenants (banks)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/tenants/` | List all banks |
| `POST` | `/api/tenants/` | Register a new bank |
| `GET` | `/api/tenants/{id}` | Bank details |
| `PATCH` | `/api/tenants/{id}` | Update configuration |
| `DELETE` | `/api/tenants/{id}` | Delete bank and all its data |
| `GET` | `/api/tenants/{id}/stats` | Graph statistics for a bank |

### Prometeo (open banking)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/prometeo/providers` | List available banking providers |
| `POST` | `/api/prometeo/login` | Login to bank via Prometeo |
| `POST` | `/api/prometeo/login-procedure` | Handle 2FA / security questions |
| `GET` | `/api/prometeo/accounts` | Get accounts |
| `GET` | `/api/prometeo/accounts/{num}/movements` | Get movements |
| `GET` | `/api/prometeo/credit-cards` | Get credit cards |
| `GET` | `/api/prometeo/info` | Get personal info |
| `POST` | `/api/prometeo/sync` | **Full sync** — pull data and run fraud pipeline |
| `GET` | `/api/prometeo/transfers/destinations` | Transfer destinations |
| `GET` | `/api/prometeo/transfers/form-fields` | Required transfer fields |
| `GET` | `/api/prometeo/transfers/mfa-methods` | MFA methods for transfers |
| `POST` | `/api/prometeo/transfers/preprocess` | Preprocess transfer |
| `POST` | `/api/prometeo/transfers/preprocess/retry` | Retry failed preprocess |
| `POST` | `/api/prometeo/transfers/confirm` | Confirm transfer |
| `POST` | `/api/prometeo/transfers/detail` | Transfer details |
| `POST` | `/api/prometeo/transfers/validate-account` | Validate destination account |
| `GET` | `/api/prometeo/transfers/enroll-form` | Enrollment form fields |
| `POST` | `/api/prometeo/transfers/enroll` | Pre-enroll destination account |
| `POST` | `/api/prometeo/transfers/enroll/confirm` | Confirm enrollment |
| `POST` | `/api/prometeo/transfers/enroll/remove` | Remove enrolled account |
| `POST` | `/api/prometeo/transfers/batch/preprocess` | Batch transfer preprocess |
| `POST` | `/api/prometeo/transfers/batch/confirm` | Batch transfer confirm |
| `POST` | `/api/prometeo/transfers/batch/detail` | Batch transfer details |
| `GET` | `/api/prometeo/transfers/logs` | Transfer logs |
| `GET` | `/api/prometeo/transfers/logs/{id}` | Transfer log detail |
| `POST` | `/api/prometeo/logout` | Close Prometeo session |

### Training (cross-tenant intelligence)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/training/patterns` | Anonymized fraud patterns |
| `GET` | `/api/training/topology-signatures` | Graph topology features |
| `GET` | `/api/training/risk-features` | Risk feature vectors |
| `GET` | `/api/training/cross-tenant/correlations` | Cross-bank correlations |

---

## Dashboard

The dashboard is a decision platform for compliance analysts.

### Alert Queue (main screen)

The analyst's home. Prioritized alerts sorted by risk score. Filters for verdict, country, score threshold. Click any row to investigate.

### Case View (investigation screen)

Everything needed to make a decision, organized in tabs:

- **Narrative** — auto-generated summary of what happened and what the system recommends
- **Risk signals** — triggered rules with severity badges (CRITICAL / HIGH / MEDIUM)
- **Agent scores** — risk score from each of the 5 analysis agents
- **Graph** — interactive vis.js network centered on the suspect account
- **AI reasoning** — step-by-step numbered explanation of why this is suspicious
- **ROS report** — regulatory report with button to open printable version
- **Audit log** — full history of analyst actions
- **Decision panel** — Confirm Fraud / False Positive / Escalate (always visible)

### Metrics (manager view)

KPIs, verdict donut chart, pattern distribution, and per-bank statistics table.

---

## Regulatory framework

| Country | Regulations |
|---------|------------|
| **Uruguay** | Ley 19.574, BCU, SENACLAFT, UIAF |
| **Argentina** | Ley 25.246/26.683, BCRA Com. A 6399, UIF |
| **International** | GAFI/GAFILAT, OFAC, UN, EU sanctions |

- Documents: Cedula (UY), DNI (AR)
- Account identifiers: CBU/CVU
- Reports: ROS (Reporte de Operacion Sospechosa)
- ROS destinations: UIAF (Uruguay), UIF (Argentina)

---

## How scoring works

### Confidence score

```
C = (W_sentinel * S_sentinel + W_osint * S_osint + W_patterns * S_patterns
     + W_historian * S_historian + W_jurist * S_jurist) / sum(weights)
```

### Verdicts

| Score | Verdict | Action |
|-------|---------|--------|
| < 0.40 | DISCARD | Auto-dismiss |
| 0.40 - 0.65 | MONITOR | Watch 72 hours |
| 0.65 - 0.85 | ESCALATE | Send to human analyst |
| >= 0.85 | BLOCK | Automatic block + ROS |

### Risk multipliers

| Factor | Multiplier |
|--------|-----------|
| Amount > USD 10,000 | x1.20 |
| Account < 30 days old | x1.10 |
| VPN/TOR connection | x1.15 |
| GAFI high-risk destination | x1.20 |
| GAFI grey-list destination | x1.15 |
| PEP (Politically Exposed Person) | x1.10 |
| Sanctions list match | x1.20 |
| Client > 5 years, no incidents | x0.90 |
| Client > 2 years, no incidents | x0.80 |

---

## Project structure

```
sentinel-swarm/
├── src/sentinel_swarm/
│   ├── agents/              # 6 AI agents
│   │   ├── sentinel.py      # Graph topology monitor
│   │   ├── osint.py         # OSINT identity validator
│   │   ├── patterns.py      # Attack pattern classifier
│   │   ├── historian.py     # Historical precedent search
│   │   ├── jurist.py        # Legal/compliance evaluator
│   │   └── executor.py      # Action executor
│   ├── api/
│   │   ├── app.py           # FastAPI application
│   │   ├── deps.py          # Shared state and persistence
│   │   └── routes/
│   │       ├── alerts.py    # Alert queue and decisions
│   │       ├── cases.py     # Case management
│   │       ├── events.py    # Event processing
│   │       ├── graph.py     # Graph exploration
│   │       ├── health.py    # Health checks
│   │       ├── prometeo.py  # Prometeo open banking
│   │       ├── reports.py   # ROS/SAR generation
│   │       ├── tenants.py   # Bank management
│   │       └── training.py  # Cross-tenant intelligence
│   ├── config/              # Settings via environment variables
│   ├── graph/               # Neo4j client and tenant manager
│   ├── ingestion/           # Kafka consumer and enrichment
│   ├── integrations/
│   │   └── prometeo.py      # Prometeo API client (full coverage)
│   ├── models/              # Pydantic data models
│   ├── orchestrator/        # LangGraph pipeline
│   ├── tools/               # Agent tools
│   └── utils/               # Logging
├── tests/                   # Unit tests
├── docker/
│   ├── docker-compose.yml   # Neo4j, Kafka, Redis, ChromaDB
│   └── neo4j/init.cypher    # Graph constraints and indexes
├── data/                    # Persisted cases
├── dashboard.py             # Streamlit dashboard
├── seed.py                  # Small seed (pipeline mode)
├── seed_massive.py          # Large seed (55K cases)
├── start.sh                 # One-command startup
├── pyproject.toml           # Python dependencies
├── .env.example             # Environment template
└── .gitignore
```

---

## Running tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

---

## Limitations

This is a proof of concept. Key limitations:

- **No real LLM calls in demo mode** — agents use rule-based heuristics when API keys are not configured
- **In-memory + JSON persistence** — not a proper database for cases
- **No authentication** — the API has no auth layer
- **No encryption** — PII is not encrypted at rest
- **No rate limiting** — API endpoints are unprotected
- **Single-node** — no horizontal scaling
- **Kafka is optional** — demo mode bypasses Kafka
- **OSINT is simulated** — OSINT agent uses heuristics without real API keys

For production: add encryption, authentication (JWT/OAuth), RBAC, persistent storage (PostgreSQL), monitoring, and a full security review.

---

## Contributing

Contributions are welcome. Please open an issue first to discuss changes.

Areas where help is needed:
- Real OSINT integrations (AbuseIPDB, MaxMind, HIBP)
- Production persistence (PostgreSQL for cases)
- Authentication and RBAC
- Frontend rewrite in Next.js for production UX
- Additional fraud patterns and detection rules
- Performance optimization for large graphs
- Support for more LATAM countries (BR, CL, CO, MX, PE)

---

## Author

Built by **[Kevin Correa](https://www.linkedin.com/in/kevin--correa/)**.

## License

MIT

---

## Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) — agent orchestration
- [Neo4j](https://neo4j.com/) — graph database and GDS algorithms
- [Prometeo](https://prometeoapi.com/) — open banking API for LATAM
- [vis.js](https://visjs.org/) — interactive graph visualization
- [Streamlit](https://streamlit.io/) — dashboard prototyping

Built as a research project exploring multi-agent AI systems for financial crime detection in Latin America.
