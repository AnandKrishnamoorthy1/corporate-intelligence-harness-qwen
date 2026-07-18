# Architecture - Corporate Intelligence Harness

## Overview

Corporate Intelligence Harness is a Streamlit and FastAPI application backed by a LangGraph workflow. Qwen classifies each request, routes it to a specialized path, and produces a structured response from live financial evidence.

```text
User
  |
  v
Streamlit UI (frontend.py)
  |
  | HTTP + NDJSON
  v
FastAPI API (backend.py)
  |
  v
LangGraph orchestrator (orchestrator.py)
  |
  +-- research -----> investment committee
  +-- direct_trade -> approval request
  +-- portfolio ----> portfolio risk analysis
  +-- general_q ----> conversational response
  |
  v
approval_execution -> reporting -> response
```

## Request Routing

The `triage_node` uses structured Qwen output to select one of four paths.

| Route | Responsibility |
|---|---|
| `research` | Fetch market evidence and run the adversarial investment committee. |
| `direct_trade` | Parse an order request and create a human approval gate. |
| `portfolio` | Read positions and calculate portfolio and concentration risk. |
| `general_q` | Answer conversational questions using retained context. |

All routes converge on `approval_execution_node` and then `reporting_node`. An order is sent to a broker only when an approval exists and has been explicitly approved.

## Research Pipeline

`app/tools/external_tools.py` fetches quote and fundamental data through the Yahoo Finance MCP client while `app/tools/sec_tools.py` retrieves SEC filing data. The fetches are combined into one evidence payload.

```text
Ticker
  +-- Yahoo Finance MCP: quote and fundamentals
  +-- SEC EDGAR: recent filing metrics
  |
  v
Shared evidence payload
  +-- Bull Analyst
  +-- Bear Auditor
  |
  v
Portfolio Director verdict
```

The Bull Analyst and Bear Auditor run concurrently during each debate round. Both receive the same evidence and prior-round transcript. The Portfolio Director then returns a structured verdict containing the thesis, confidence, supporting arguments, risks, and dissent.

The shared evidence contract limits each persona to the facts supplied by the tools. The final report and source payload are returned together so the frontend can display citations beside the analysis.

## Trading Boundary

The trading package exposes a common `BaseBroker` interface with two implementations:

| Implementation | Purpose |
|---|---|
| `MockSimulationEngine` | Paper trading backed by `simulation_ledger.json`. |
| `RobinhoodMCPClient` | Broker-backed execution through Robinhood MCP. |

`app/trading/broker_factory.py` selects the broker. Simulation mode is always available; live execution additionally requires `ROBINHOOD_TRADING_ENABLED=true` and an authenticated admin session. Public or unauthenticated sessions fall back to simulation.

The execution sequence is:

1. A research or direct-trade path creates an approval request.
2. The frontend displays approve and reject controls.
3. The approval endpoint records the human decision.
4. The execute endpoint revalidates the approval.
5. The selected broker places the order and returns fill details.

## Streaming API

`POST /api/analyze/stream` runs the synchronous LangGraph workflow in a background thread. Loguru messages are placed on a queue and emitted as newline-delimited JSON while the graph is running.

```json
{"type":"log","message":"Research node started"}
{"type":"result","result":{"status":"completed"}}
```

The Streamlit client consumes each line as it arrives, updates the visible progress log, then renders the final report, sources, portfolio state, or approval request.

## Main Components

| Path | Responsibility |
|---|---|
| `frontend.py` | Streamlit interface, session context, citations, and approval controls. |
| `backend.py` | FastAPI endpoints, streaming bridge, approvals, execution, and portfolio API. |
| `orchestrator.py` | Graph state, routing, workflow nodes, and report assembly. |
| `app/agents/investment_committee.py` | Bull, Bear, and Director deliberation. |
| `app/llm/qwen_integration.py` | Qwen client and structured-output helpers. |
| `app/tools/yahoo_finance_mcp_client.py` | Yahoo Finance MCP transport and tool calls. |
| `app/tools/sec_tools.py` | SEC EDGAR filing extraction. |
| `app/trading/` | Broker interface, simulation, OAuth, and Robinhood integration. |
| `app/skills/skill_registry.py` | Discovery and execution of portfolio and risk skills. |
| `config/settings.py` | Typed environment configuration. |

## Repository Layout

```text
corporate-intelligence-harness/
|-- app/
|   |-- agents/
|   |-- llm/
|   |-- prompts/
|   |-- skills/
|   |-- tools/
|   `-- trading/
|-- config/
|-- deployment/
|-- docker/
|-- skills/
|-- backend.py
|-- frontend.py
|-- orchestrator.py
|-- test_backend.py
|-- s.yaml
`-- requirements.txt
```

## Deployment

The frontend can run on Streamlit Community Cloud. The backend is configured for Alibaba Cloud Function Compute through `s.yaml`, `bootstrap`, and `alibaba_handlers.py`. Docker definitions remain available for local or container-hosted deployments.

See [deployment/DEPLOYMENT_ALIBABA.md](deployment/DEPLOYMENT_ALIBABA.md) for the cloud deployment procedure.

## Security Invariants

- Secrets are supplied through environment variables and are excluded from Git.
- Public deployments should set `BROKER_TYPE=simulation`.
- Live trading requires the explicit live-trading flag and an admin session.
- Analysis never bypasses the approval store to execute an order.
- Citations are derived from the same evidence payload supplied to the agents.
- Generated logs, caches, and local credentials are ignored by Git.
