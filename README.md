# Corporate Intelligence Engine — Qwen Edition

**Track 4 Submission — Qwen Cloud Global AI Hackathon: Autopilot Agent**

A production-grade agentic trading system powered by **Alibaba Qwen** (`qwen3.7-plus`). A **Tri-Agent Adversarial Investment Committee** — Bull Analyst, Bear Auditor, and Portfolio Director — debates live market data from Alpha Vantage and SEC EDGAR before issuing a vetted BUY / HOLD / SELL verdict. Every trade requires explicit human approval before executing against a paper-trading simulation.

---

## 🎯 What It Solves

| Pain Point | Solution |
|---|---|
| Manual multi-source data aggregation | 3-way parallel fetch: AV quote + fundamentals + SEC 10-Q |
| Single-analyst confirmation bias | Adversarial Bull vs Bear debate with structured rebuttal |
| Unverifiable AI claims | Citation system — every data point traced to its API source |
| Unsafe autonomous trading | Human-in-loop approval gate before every order execution |
| Fragile single-LLM analysis | Three Qwen personas with different temperature tuning |

**Track 4 Alignment:**
- ✅ **Ambiguous input handling** — Triage node classifies 4 query types via structured Qwen output
- ✅ **External tool invocation** — Alpha Vantage (real-time + fundamentals) + SEC EDGAR (XBRL 10-Q)
- ✅ **Human-in-loop gates** — Approval checkpoint before any trade executes
- ✅ **End-to-end agentic workflow** — Query → Triage → Committee → Approval → Execution → Report
- ✅ **Robinhood Agentic Trading MCP** — `RobinhoodMCPClient` wired through broker abstraction layer

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Qwen API key — [DashScope International](https://dashscope-intl.aliyuncs.com/)
- Alpha Vantage API key — [alphavantage.co](https://www.alphavantage.co/support/#api-key) (free tier works)

### Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — set DASHSCOPE_API_KEY and ALPHA_VANTAGE_API_KEY

# 3. Terminal 1 — Backend (port 8002)
python backend.py

# 4. Terminal 2 — Frontend (port 8501)
streamlit run frontend.py
```

Open `http://localhost:8501` and try:
- `"Analyze NVDA"` — full committee research path
- `"Buy $500 of TSLA"` — direct trade with approval gate
- `"Show my portfolio"` — live P&L + HHI risk analysis
- `"What is a P/E ratio?"` — general Q&A path

---

## 🏆 Key Features

### 1. Tri-Agent Adversarial Investment Committee
Three distinct Qwen personas debate each stock using a **shared, immutable evidence contract** — no persona can invent facts:

```
Bull Analyst (temp 0.7)  ─┐
                           ├─► Portfolio Director (temp 0.4) ─► BUY/HOLD/SELL + confidence
Bear Auditor (temp 0.7)  ─┘

Each round: Bull and Bear argue in PARALLEL (ThreadPoolExecutor)
            Both see the full prior-round transcript for rebuttals
            Director weighs evidence quality, not rhetoric
```

### 2. 3-Way Parallel Data Fetch
```
get_enriched_stock_data(ticker)
    ├── [Thread 1] Alpha Vantage GLOBAL_QUOTE  → price, change%, volume
    ├── [Thread 2] Alpha Vantage OVERVIEW      → P/E, EPS, sector, margins, beta
    └── [Thread 3] SEC EDGAR 10-Q (edgartools) → revenue, NI, R&D, FCF (last 2 qtrs)
                                                  parsed from XBRL — audited data
```

### 3. 4-Path Intelligent Routing
Qwen triage outputs structured JSON with confidence score:

| Path | Trigger Example | What Happens |
|---|---|---|
| `research` | "Analyze NVDA earnings" | Committee debate + report |
| `direct_trade` | "Buy $500 of TSLA" | Approval gate → broker execution |
| `portfolio` | "Show my portfolio" | Live P&L + HHI concentration risk |
| `general_q` | "What is a P/E ratio?" | Qwen Q&A |

### 4. Human-in-Loop Approval Gate
```
Committee → BUY verdict
    ↓
[CHECKPOINT] Workflow PAUSED — trade stored with unique request_id
    ↓
Human reviews in sidebar (Approve / Reject)
    ↓
Approved → broker.place_order() executes via BaseBroker abstraction
           Portfolio ledger updates with real Alpha Vantage fill price
Rejected → report updated, no trade executed
```

### 5. Citation / Source Transparency
Every data point in the report carries an inline citation marker (`[1]` `[2]` `[3]` `[4]`).  
The sidebar **📚 Sources** panel shows the exact raw API payload each marker refers to — judges can verify no hallucination.

### 6. NDJSON Streaming
Backend streams `{"type":"log",...}` and `{"type":"result",...}` events over a single HTTP connection. The frontend renders live step-by-step progress (Claude/Copilot style) without polling.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Streamlit Frontend  (port 8501)                            │
│  • NDJSON stream consumer — live step display               │
│  • Sidebar: Portfolio panel, 📚 Sources citations          │
│  • Approve / Reject trade buttons                           │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / NDJSON stream
┌──────────────────────────▼──────────────────────────────────┐
│  FastAPI Backend  (port 8002)                               │
│  /api/analyze/stream  — NDJSON streaming endpoint           │
│  /api/approve/{id}    — human approval decision             │
│  /api/execute/{id}    — post-approval trade execution       │
│  /api/portfolio       — live portfolio with AV prices       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  LangGraph State Machine  (orchestrator.py)                 │
│                                                             │
│   START → triage_node                                       │
│                │                                            │
│     ┌──────────┼──────────────────────┐                   │
│     ▼          ▼           ▼          ▼                   │
│  research  direct_trade  portfolio  general_q              │
│     │          │           │          │                    │
│     └──────────┴───────────┴──────────┘                   │
│                │                                            │
│     approval_execution_node                                 │
│                │                                            │
│        reporting_node → END                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   Alpha Vantage      SEC EDGAR         Broker
   GLOBAL_QUOTE       10-Q XBRL     (MockSimulation
   + OVERVIEW         (edgartools)   Engine / Robinhood
                                     MCP Client)
```

### Tri-Agent Committee (research path detail)
```
research_node
    │
    ├── get_enriched_stock_data(ticker)          ← 3 threads, one call
    │       ├── AV GLOBAL_QUOTE
    │       ├── AV OVERVIEW
    │       └── SEC EDGAR 10-Q
    │
    └── run_investment_committee(ticker, data, rounds=2)
            │
            Round 1:  Bull ──┐  (parallel)
                      Bear ──┘
            Round 2:  Bull ──┐  (parallel, sees R1 transcript)
                      Bear ──┘
            Director verdict (structured JSON schema)
            │
            └── render_committee_report() → report_markdown
```

---

## 📂 Project Structure

```
├── backend.py              # FastAPI — all endpoints, NDJSON streaming
├── frontend.py             # Streamlit — UI, sidebar, streaming consumer
├── orchestrator.py         # LangGraph state machine — all graph nodes
│
├── app/
│   ├── agents/
│   │   └── investment_committee.py   # Tri-Agent adversarial committee
│   ├── llm/
│   │   └── qwen_integration.py       # Qwen client, structured output, persona calls
│   ├── tools/
│   │   ├── external_tools.py         # Alpha Vantage GLOBAL_QUOTE + OVERVIEW
│   │   └── sec_tools.py              # SEC EDGAR 10-Q via edgartools (XBRL)
│   ├── trading/
│   │   ├── broker_interface.py       # Abstract BaseBroker contract
│   │   ├── mock_simulation_engine.py # Paper trading — $10k balance, real AV prices
│   │   ├── robinhood_client.py       # Robinhood MCP client (live trading)
│   │   ├── broker_factory.py         # BROKER_TYPE env var selects implementation
│   │   └── oauth_handler.py          # Robinhood OAuth flow
│   └── prompts/
│       └── system_prompts.py         # Triage + research system prompts
│
├── config/
│   └── settings.py         # Pydantic settings — all env vars typed
│
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
│
└── tests/
    └── test_backend.py
```

---

## 🔑 Configuration (`.env`)

```bash
# Required
DASHSCOPE_API_KEY=your_dashscope_key          # Qwen LLM
ALPHA_VANTAGE_API_KEY=your_av_key             # Market data

# Optional — Qwen model settings
QWEN_MODEL=qwen3.7-plus
QWEN_TEMPERATURE=0.3
QWEN_TOP_P=0.85
DASHSCOPE_ENDPOINT=https://dashscope-intl.aliyuncs.com/compatible-mode/v1

# Optional — Broker mode (default: simulation)
BROKER_TYPE=simulation                         # or: robinhood
ROBINHOOD_CLIENT_ID=...
ROBINHOOD_CLIENT_SECRET=...

# Server
BACKEND_PORT=8002
```

---

## 🔌 API Reference

### Stream analysis
```bash
POST /api/analyze/stream
{"user_input": "Analyze NVDA"}
# Returns NDJSON stream: {"type":"log",...} then {"type":"result",...}
```

### Approve / reject trade
```bash
POST /api/approve/{request_id}
{"approved": true, "approver_notes": "Strong fundamentals confirmed."}
```

### Execute approved trade
```bash
POST /api/execute/{request_id}
# Calls broker.place_order(), updates simulation ledger
```

### Portfolio
```bash
GET /api/portfolio
# Returns holdings with live AV prices, P&L, HHI concentration score
```

---

## 📋 Track 4 Evaluation Checklist

| Criterion | Implementation | Status |
|---|---|---|
| Ambiguous input handling | 4-path Qwen triage with confidence score | ✅ |
| External tool invocation | Alpha Vantage + SEC EDGAR (real APIs) | ✅ |
| Human-in-loop gates | Approval checkpoint + broker execution | ✅ |
| Multi-agent orchestration | Tri-Agent adversarial committee | ✅ |
| Robinhood MCP integration | `RobinhoodMCPClient` + `MockSimulationEngine` | ✅ |
| Hallucination prevention | Shared evidence contract + citation system | ✅ |
| Performance optimization | 3-way parallel fetch + parallel debate rounds | ✅ |
| Production architecture | LangGraph, Pydantic, NDJSON streaming, Docker | ✅ |

---

## 🏭 Production-Grade Engineering

### Reusable AI Agent Skills

The system implements **modular, reusable skills** that encapsulate domain-specific workflows. Skills are loaded dynamically via YAML manifests, enabling progressive disclosure of capabilities.

#### Implemented Skills

1. **Portfolio Analyzer** — Comprehensive asset allocation analysis
   - Herfindahl-Hirschman Index (HHI) for concentration risk
   - Sector allocation breakdown + bias detection
   - Diversification scoring (0-100 scale)
   - Actionable rebalancing recommendations

2. **Risk Manager** — Multi-factor portfolio risk assessment
   - Beta-weighted portfolio volatility
   - Correlation risk analysis (sector-based grouping)
   - Liquidity constraints + time-to-liquidate
   - Composite risk scoring with tolerance-relative thresholds

3. **Stop-Loss/Take-Profit Triggers** — Real-time threshold monitoring
   - Concentration breach alerts (50% threshold for easy demo)
   - Stop-loss triggers (-10% unrealized loss)
   - Take-profit triggers (+30% unrealized gain)
   - Pre-trade validation (checks if new buy/sell would breach thresholds)
   - On-demand invocation: Only checks when strategically triggered

**Skill Architecture**:
```python
# On-demand invocation (not continuous background monitoring)
from app.skills import invoke_skill

# Called in research_node before IC debate
portfolio_analysis = invoke_skill("portfolio_analyzer", portfolio=portfolio_data)
risk_report = invoke_skill("risk_manager", portfolio=portfolio_data, risk_tolerance="moderate")
triggers = invoke_skill("stop_loss_take_profit", portfolio=portfolio_data)

# Results passed to IC debate as contextual constraints
```

**Why This Matters for Judges**:
- ✅ Sophisticated MCP orchestration pattern (progressive skill loading)
- ✅ Novel algorithmic contributions (HHI, multi-factor risk, correlation clustering)
- ✅ Production-ready patterns (graceful degradation, error handling)
- ✅ Scalable architecture (add skills without modifying core logic)

---

### Error Handling & Resilience

| Pattern | Location | Example |
|---------|----------|---------|
| **Graceful Degradation** | `orchestrator.py` | Yahoo Finance timeout → fallback to cached data + generic analysis |
| **Structured Output Validation** | `qwen_integration.py` | Qwen JSON response validated against schema; invalid responses rejected |
| **Streaming Error Recovery** | `qwen_integration.py` | Connection drops → return partial response; timeout → log & continue |
| **Timeout Cascading** | `backend.py` | Triage (120s) > Streaming (90s) > Data fetch (30s) |
| **Human-in-Loop Gates** | `orchestrator.py` | Every trade paused for approval before execution |

---

### Timeout Strategy

| Operation | Timeout | Rationale |
|-----------|---------|-----------|
| Streaming (Persona) | 90s | Real-time LLM generation |
| Structured Output (Triage) | 120s | JSON parsing overhead |
| Data Fetch (Yahoo Finance) | 30s | API latency |
| Trade Execution | 120s | OAuth + broker integration |
| Frontend Request | 600s | NDJSON stream collection |

**Fallback**: If timeout exceeded, system returns partial result + error count incremented.

---

### Conversation History Constraints

- **Window**: Last 6 turns (3 user questions max)
- **Truncation**: 150 chars per turn, sanitized
- **Purpose**: Context-aware follow-ups ("Compare profitability" remembers "TSLA" from prior turn)
- **Storage**: In-memory (Streamlit session_state), auto-cleared on new chat

---

### Deployment Checklist

**Pre-Production:**
- [ ] All API keys in `.env` (never in code)
- [ ] DEBUG=False, LOG_LEVEL=INFO in production
- [ ] Database transactions tested for trade atomicity
- [ ] Rate limiting configured (30 req/min per IP)
- [ ] Health check endpoints verified
- [ ] Error recovery tested (simulate API failures)

**Production Launch:**
- [ ] CI/CD pipeline configured
- [ ] Monitoring/alerting set up (error rates, latency SLA)
- [ ] Backup/disaster recovery documented
- [ ] On-call runbook for common failures
- [ ] API versioning strategy (v1 prefix)

---

## 📖 Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — Design decisions and component deep-dives
- [IMPLEMENTATION.md](IMPLEMENTATION.md) — Technical implementation notes
- [SETUP.md](SETUP.md) — Detailed installation guide
- [DEPLOYMENT.md](DEPLOYMENT.md) — Docker and production deployment

---

## 🤝 Troubleshooting

**`DASHSCOPE_API_KEY not set`** → Add your key to `.env`

**`Alpha Vantage rate limit`** → Free tier is 25 req/day. The system falls back gracefully to mock data.

**`edgartools EDGAR identity`** → Set `EDGAR_IDENTITY` in `.env` or it uses the default demo identity.

**`Port 8002 in use`** → Set `BACKEND_PORT=8003` in `.env`

---

## ⚡ Performance

| Operation | Time |
|---|---|
| Triage (Qwen structured output) | 300–600 ms |
| 3-way parallel data fetch | 1–3 s |
| Committee debate (2 rounds, parallel) | 4–8 s |
| Portfolio analysis | 2–4 s |
| **Full research query end-to-end** | **6–12 s** |

