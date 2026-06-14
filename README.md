# corporate-intelligence-engine

A resilient AI state graph orchestrating autonomous ReAct agents for deep financial market research and automated corporate intelligence delivery on AWS.

## 🎯 Quick Start

### Local Development (5 minutes)

```bash
# Install dependencies
pip install -r requirements.txt

# Terminal 1: Start FastAPI backend
uvicorn backend:app --reload

# Terminal 2: Start Streamlit frontend
streamlit run frontend.py
```

Open `http://localhost:8501` in your browser and start analyzing financial queries!

---

## 📋 Project Overview

This project implements a complete AI stack for financial research:

| Layer | Component | Technology |
|-------|-----------|------------|
| **Orchestration** | State Machine | LangGraph + Pydantic |
| **Backend API** | REST Interface | FastAPI + Uvicorn |
| **Frontend UI** | Web Interface | Streamlit + Requests |

### Architecture

```
User Interface (Streamlit)
        ↕ HTTP REST
Backend API (FastAPI)
        ↕
State Graph Orchestrator (LangGraph)
        ↕
Autonomous Agent Nodes
```

---

## 🏗️ Core Architecture

### 1. **Orchestrator** (`orchestrator.py`)
State machine with deterministic, auditable execution flows:
- **Triage Node**: Routes queries to appropriate handler
- **Research Node**: Gathers financial data
- **General Q Node**: Handles general knowledge questions
- **Reporting Node**: Consolidates findings

**State Model (Pydantic):**
```python
class AgentState(BaseModel):
    user_input: str
    current_target_ticker: str
    routing_decision: str
    research_data: Dict[str, Any]
    report_markdown: str
    error_count: int
```

### 2. **Backend API** (`backend.py`)
FastAPI REST service exposing the orchestrator:
- **POST /api/analyze** - Execute analysis with logs
- **GET /health** - Health check
- **GET /api/routes** - Available routing paths
- **GET /docs** - Interactive API documentation

**Request/Response Models:**
```python
class AnalysisRequest(BaseModel):
    user_input: str

class AnalysisResponse(BaseModel):
    status: str
    routing_decision: str
    logs: List[str]
    report_markdown: str
    execution_time_ms: float
```

### 3. **Frontend UI** (`frontend.py`)
Streamlit web application for interactive analysis:
- Real-time chat interface
- Live agent execution trace
- Markdown report rendering
- Execution metrics display

---

## Core Architecture
- **Resilient state graph orchestration** for deterministic, restart-safe agent workflows.
- **Autonomous ReAct research agents** for iterative market signal discovery, validation, and synthesis.
- **Automated intelligence delivery on AWS** for scalable, event-driven report generation and distribution.
