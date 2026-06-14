# Corporate Intelligence Engine - Walking Skeleton

A modular AI State Graph system for autonomous financial research and corporate intelligence gathering.

## Architecture Overview

This walking skeleton demonstrates a production-ready pattern for building resilient, event-driven AI systems using:

- **State Management**: Pydantic BaseModel for type-safe, validated state
- **Graph Orchestration**: LangGraph for deterministic, auditable execution flows
- **Structured LLM Output**: RouterDecision model for enforcing schema compliance
- **Modular Nodes**: Independent, testable components for different reasoning tasks
- **Conditional Routing**: Dynamic path selection based on classified input

## Project Structure

```
corporate-intelligence-engine/
├── orchestrator.py           # Main state graph implementation
├── requirements.txt          # Python dependencies
├── README.md                 # This file
└── QUICKSTART.md            # Setup and execution instructions
```

## Core Components

### 1. **State Model** (`AgentState`)
Central Pydantic model tracking execution context:
- `user_input`: Original query
- `current_target_ticker`: Extracted stock symbol
- `routing_decision`: "research", "general_q", or "error"
- `research_data`: Collected financial data
- `report_markdown`: Final formatted output
- `error_count`: Error tracking for reliability

### 2. **Router Decision Model** (`RouterDecision`)
Structured output schema enforced on LLM responses:
- `ticker`: Extracted stock symbol
- `routing_path`: Deterministic next node
- `confidence`: Decision confidence (0.0-1.0)
- `reasoning`: Explainable AI trace

### 3. **Nodes**

#### **Triage Node**
- Entry point that classifies user input
- Extracts stock tickers using heuristics (production: use LLM)
- Outputs structured `RouterDecision`
- Routes to appropriate downstream node

#### **Research Node (Stub)**
- Handles financial research requests
- Simulates multi-source data gathering
- Enriches state with mock financial data (real APIs in production)
- Passes enriched state forward

#### **General Q Node (Stub)**
- Handles non-research queries
- Can integrate knowledge bases or QA models
- Generates contextual responses

#### **Reporting Node**
- Consolidates findings into polished report
- Formats markdown output with metadata
- Ready for delivery to stakeholders

### 4. **Conditional Routing**
After the Triage Node, the `route_after_triage()` function examines `state["routing_decision"]` and directs execution:
```
triage → (research | general_q) → reporting → END
```

## Execution Flow with Logging

The system produces highly auditable logs showing:

```
[ENTERING TRIAGE NODE]
  User Input: Analyze latest earnings for NVDA
  Invoking LLM for structured routing decision...
  LLM Response: { ticker: "NVDA", routing_path: "research", confidence: 0.92, ... }
  Extracted Ticker: NVDA
  Routing Decision: research
[TRIAGE NODE COMPLETE]

[CONDITIONAL ROUTING] Decision: research
[CONDITIONAL EDGE] Taking RESEARCH path

[ENTERING RESEARCH NODE]
  Target Ticker: NVDA
  Simulating data gathering for NVDA...
  Retrieved data: { ticker: "NVDA", current_price: 150.25, market_cap_b: 2500.0, ... }
[RESEARCH NODE COMPLETE]

[ENTERING REPORTING NODE]
[REPORTING NODE COMPLETE]

FINAL REPORT:
# Financial Research Report: NVDA
## Company Overview
...
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Walking Skeleton

```bash
python orchestrator.py
```

This executes three test cases:
- **Test 1**: Research query with explicit ticker → research path
- **Test 2**: Research query without ticker → research path with fallback
- **Test 3**: General question → general_q path

### 3. Observe Execution Flow

The output includes:
- State transitions at each node
- LLM routing decisions (mocked with heuristics)
- Mock data gathering for research
- Final formatted reports

## State Management Pattern

```python
# Initial state
state = {
    "user_input": "Analyze NVDA earnings",
    "current_target_ticker": "",
    "routing_decision": "",
    "research_data": {},
    "report_markdown": "",
    "error_count": 0
}

# After Triage Node
state = {
    "user_input": "Analyze NVDA earnings",
    "current_target_ticker": "NVDA",          # ← Extracted
    "routing_decision": "research",           # ← Decision
    "research_data": {},
    "report_markdown": "",
    "error_count": 0
}

# After Research Node
state = {
    "user_input": "Analyze NVDA earnings",
    "current_target_ticker": "NVDA",
    "routing_decision": "research",
    "research_data": {                        # ← Enriched
        "ticker": "NVDA",
        "current_price": 150.25,
        "pe_ratio": 28.5,
        ...
    },
    "report_markdown": "",
    "error_count": 0
}

# After Reporting Node
state = {
    ...
    "report_markdown": "# Financial Research Report: NVDA\n..."  # ← Final output
}
```

## Extending the Walking Skeleton

### Add Real LLM Integration

Replace the `mock_extract_routing_decision()` function to call an actual LLM:

```python
from openai import OpenAI

def extract_routing_decision(user_input: str) -> RouterDecision:
    client = OpenAI()
    response = client.beta.messages.create(
        model="gpt-4",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"Classify this query: {user_input}"
            }
        ],
        response_model=RouterDecision,
    )
    return response.parsed
```

### Add Real Data Sources

Extend the `research_node()` to call actual financial APIs:

```python
import yfinance

def research_node(state: GraphState) -> GraphState:
    ticker = state["current_target_ticker"]
    stock = yfinance.Ticker(ticker)
    
    state["research_data"] = {
        "current_price": stock.info["currentPrice"],
        "market_cap": stock.info["marketCap"],
        "pe_ratio": stock.info["trailingPE"],
        ...
    }
    
    return state
```

### Add Multi-Step Reasoning

Implement a Research Agent that iterates:

```python
def research_node(state: GraphState) -> GraphState:
    """Implement ReAct pattern for iterative research."""
    ticker = state["current_target_ticker"]
    
    # Step 1: Gather financial metrics
    # Step 2: Analyze recent news
    # Step 3: Compare to peers
    # Step 4: Synthesize conclusions
    
    return state
```

### Add Persistent Storage

Store final reports to database/file system:

```python
def reporting_node(state: GraphState) -> GraphState:
    # Generate report
    report = generate_report(state)
    
    # Save to database or S3
    save_to_storage(report)
    
    state["report_markdown"] = report
    return state
```

## Key Design Principles

1. **Deterministic Execution**: Same input always produces same execution path
2. **Audit Trail**: Every node logs its state transitions
3. **Type Safety**: Pydantic models enforce schema compliance
4. **Modular Design**: Each node is independent and testable
5. **Graceful Error Handling**: Error counter tracks issues across execution
6. **Conditional Routing**: Dynamic path selection based on data, not configuration

## Next Steps

1. Implement real LLM integration (OpenAI/Anthropic structured output)
2. Add financial data APIs (yfinance, Alpha Vantage, Refinitiv)
3. Implement ReAct research agents with tool use
4. Add data persistence (PostgreSQL, S3, MongoDB)
5. Deploy on AWS with event-driven triggers
6. Add monitoring and observability (LangSmith, Datadog)

---

**Architecture**: LangGraph state machine with Pydantic validation  
**Status**: Walking skeleton — ready for extension  
**Last Updated**: 2026-06-13
