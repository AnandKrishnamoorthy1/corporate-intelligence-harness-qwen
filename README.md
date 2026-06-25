# Corporate Intelligence Engine - Qwen Edition

**Track 4 Submission: Alibaba Hackathon**

An intelligent financial workflow automation agent that demonstrates **real external tool integration** and **human-in-loop decision gates** for autonomous business operations.

## 🎯 Hackathon Narrative

**Problem:** Financial analysts waste time manually researching stocks, retrieving data, and making trading recommendations. Each decision should be validated by human judgment before execution.

**Solution:** An AI agent that:
1. **Routes queries intelligently** - Classifies whether user wants stock analysis or general knowledge
2. **Fetches REAL financial data** - Calls Alpha Vantage API for live stock prices and metrics
3. **Generates AI analysis** - Uses Alibaba Qwen LLM to create research reports
4. **Requires human approval** - Pauses on BUY/SELL recommendations until human approves

**Track 4 Alignment:**
- ✅ **Ambiguous input handling**: "Analyze NVDA" → Routed to research path
- ✅ **External tool invocation**: Real Alpha Vantage API (not mock data)
- ✅ **Human-in-loop gates**: Approval checkpoints for critical actions
- ✅ **End-to-end workflow**: Query → Analysis → Decision → Approval → Report

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- Python 3.10+
- Qwen API key from [Alibaba DashScope](https://dashscope.aliyun.com/)
- Alpha Vantage API key from [Alpha Vantage](https://www.alphavantage.co/)

### Setup

```bash
# 1. Clone and setup
git clone <repo>
cd corporate-intelligence-engine-qwen

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Add these to .env:
# QWEN_API_KEY=your_qwen_key
# ALPHA_VANTAGE_API_KEY=your_av_key

# 4. Run in two terminals

# Terminal 1: Backend API (port 8000)
python backend.py

# Terminal 2: Frontend (port 8501)
streamlit run frontend.py
```

Open `http://localhost:8501` and try:
- "Analyze NVDA earnings" → Research path with real Alpha Vantage data
- "What is the P/E ratio formula?" → General Q&A path

---

## 🏆 Key Features

### 1. Real External Tools
```
User Query
    ↓
[REAL DATA] Alpha Vantage API
    ↓ (Returns: price, change, volume, etc.)
[QWEN] AI Analysis
```

### 2. Human-in-Loop Checkpoints
```
Qwen Recommends: BUY NVDA
    ↓
[CHECKPOINT] Workflow PAUSED
    ↓
Awaits Human Approval via /api/approve endpoint
    ↓
Action Executed or Cancelled
```

### 3. Intelligent Routing
- **Research Path**: Stock tickers, earnings, analyst ratings
- **General Q Path**: Frameworks, tutorials, definitions

### 4. Production-Ready Error Handling
- Alpha Vantage timeout → Fallback to mock data with logging
- Qwen API failures → Graceful degradation
- All errors logged with `[EXTERNAL TOOL]` prefix for traceability

---

## 📊 Workflow Example

**User:** "Should I buy NVDA?"

**Agent Steps:**
```
1. [TRIAGE NODE] → Extracts ticker: NVDA
2. [RESEARCH NODE] → Calls Alpha Vantage API for live data
   [EXTERNAL TOOL] Alpha Vantage: $NVDA 127.50 (+2.3%)
3. [QWEN ANALYSIS] → Generates research report
4. [CHECKPOINT] Recommendation: BUY (confidence: 92%)
5. [AWAITING APPROVAL] Human reviews and approves
6. [REPORTING] → Final report with approval trail
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│     Streamlit Web UI (Port 8501)            │
│  - Real-time execution logs                 │
│  - Live market data display                 │
│  - Approval decision interface              │
└────────────────┬────────────────────────────┘
                 │ HTTP REST
                 ↓
┌─────────────────────────────────────────────┐
│   FastAPI Backend (Port 8000)               │
│  - /api/analyze: Execute workflow           │
│  - /api/approve/{id}: Human decisions       │
│  - /health: Service monitoring              │
└────────────────┬────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────┐
│   LangGraph State Machine Orchestrator      │
│                                             │
│  ┌─────────────┐                          │
│  │  TRIAGE     │─→ Route to research/Q&A │
│  │  NODE       │   based on query type    │
│  └──────┬──────┘                          │
│         │                                  │
│    ┌────┴─────────────────┐              │
│    ↓                      ↓              │
│  RESEARCH            GENERAL_Q          │
│  NODE                NODE               │
│  (External Tools)    (Pure LLM)         │
│    ↓                      ↓              │
│    └────┬─────────────────┘              │
│         ↓                                 │
│  ┌──────────────────────┐               │
│  │  REPORTING NODE      │               │
│  │  Format final output │               │
│  └──────────────────────┘               │
└─────────────────────────────────────────────┘
         ↓
    External Tools:
    - Alpha Vantage API (Real market data)
    - Qwen LLM (Analysis & reasoning)
```

### State Graph Flow

```
START
  ↓
[INPUT] "Analyze NVDA"
  ↓
TRIAGE_NODE
  ├─ Qwen: Extract ticker "NVDA"
  ├─ Classify: "research" path
  └─ Set confidence
  ↓
CONDITIONAL EDGE
  ├─ If research → RESEARCH_NODE
  └─ If general_q → GENERAL_Q_NODE
  ↓
RESEARCH_NODE [EXTERNAL TOOLS]
  ├─ Call Alpha Vantage API (REAL DATA)
  ├─ Call Qwen for analysis
  ├─ [CHECKPOINT] Extract recommendation
  ├─ If BUY/SELL → Await human approval
  └─ If HOLD → Continue
  ↓
REPORTING_NODE
  ├─ Format markdown
  ├─ Include approval trail
  └─ Finalize output
  ↓
END
  ↓
[OUTPUT] Full report with logs + approval status
```

---

## 📋 Track 4 Evaluation Checklist

| Requirement | Implementation | Status |
|------------|----------------|--------|
| **Handles ambiguous input** | Triage node classifies "Analyze X" queries | ✅ |
| **Invokes external tools** | Real Alpha Vantage API integration | ✅ |
| **Human-in-loop gates** | Approval checkpoints for BUY/SELL | ✅ |
| **End-to-end workflow** | Query → Analysis → Decision → Approval → Report | ✅ |
| **Error handling** | Fallback to mock data + logging | ✅ |
| **Production ready** | Pydantic validation, CORS, structured logging | ✅ |

---

## 🔌 API Endpoints

### 1. Analysis Endpoint
```bash
POST /api/analyze
Content-Type: application/json

{
  "user_input": "Analyze NVDA earnings"
}
```

**Response (Awaiting Approval):**
```json
{
  "status": "awaiting_approval",
  "routing_decision": "awaiting_approval",
  "logs": [
    "[TRIAGE NODE] Extracted ticker: NVDA",
    "[EXTERNAL TOOL] Alpha Vantage: NVDA 127.50 (+2.3%)",
    "[CHECKPOINT] Recommendation requires human approval!"
  ],
  "report_markdown": "# Financial Analysis: NVDA...",
  "pending_approval": {
    "request_id": "NVDA-1234567890",
    "action": "BUY",
    "ticker": "NVDA",
    "reasoning": "Strong earnings + AI opportunity",
    "confidence": 0.92,
    "timestamp": "2024-06-24T14:30:00"
  },
  "approval_status": "pending",
  "execution_time_ms": 2450.3
}
```

### 2. Approval Endpoint
```bash
POST /api/approve/NVDA-1234567890
Content-Type: application/json

{
  "approved": true,
  "approver_notes": "Confirmed. Strong fundamentals for long position."
}
```

**Response:**
```json
{
  "status": "success",
  "request_id": "NVDA-1234567890",
  "approval_decision": "approved",
  "message": "Approval request approved",
  "approver_notes": "Confirmed. Strong fundamentals...",
  "next_steps": "Action will be executed immediately",
  "timestamp": "2024-06-24T14:30:15"
}
```

### 3. Health Check
```bash
GET /health
```

---

## 📂 Project Structure

```
app/
├── llm/
│   └── qwen_integration.py      # Qwen API wrapper (all LLM calls)
├── tools/
│   ├── __init__.py
│   └── external_tools.py        # Alpha Vantage integration
├── api/
├── models/
└── prompts/
    └── system_prompts.py        # Qwen prompt templates

config/
├── __init__.py
└── settings.py                  # Qwen & Alpha Vantage config

orchestrator.py                  # LangGraph state machine
backend.py                       # FastAPI REST service
frontend.py                      # Streamlit web UI

requirements.txt                 # Python dependencies
```

---

## 🔑 Configuration

Create `.env` file:
```bash
# Qwen LLM (Alibaba DashScope)
QWEN_API_KEY=your_dashscope_key
QWEN_MODEL=qwen-max
QWEN_TEMPERATURE=0.7
QWEN_TOP_P=0.85

# Alpha Vantage Financial API
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key

# Server
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
FRONTEND_PORT=8501
```

For detailed setup with Docker, see [SETUP.md](SETUP.md) and [DEPLOYMENT.md](DEPLOYMENT.md).
```

---

## 🚀 Features

✅ **AI-Powered Routing** - Smart query classification  
✅ **Professional Reports** - Markdown-formatted analysis  
✅ **Structured Output** - JSON schemas for reliability  
✅ **Error Handling** - Fallback responses for API failures  
✅ **Observable** - Comprehensive logging and tracing  
✅ **Cost-Effective** - Alibaba's competitive pricing  

---

## 📖 Documentation

- **[SETUP.md](SETUP.md)** - Installation & detailed configuration
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Design decisions
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - Technical details

---

## 🤝 Troubleshooting

**"QWEN_API_KEY not set"**
→ Add your API key to `.env` file

**"Qwen API error: 401"**
→ Check that your API key is valid in DashScope console

**"JSON parsing error"**
→ Check logs; usually indicates API connection issue

For more help, see [SETUP.md](SETUP.md#troubleshooting).

---

## 📊 Performance

- **Triage:** 200-500ms
- **Research:** 2-4s
- **General Q:** 1-3s
- **Total per query:** 3-8s
