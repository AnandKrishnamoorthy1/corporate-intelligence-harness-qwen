"""
Corporate Intelligence Engine - AI State Graph Walking Skeleton

A modular state machine orchestrating autonomous AI agents for financial research
and corporate intelligence gathering. This walking skeleton demonstrates:

1. Pydantic-based state management
2. LLM-driven routing with structured output
3. Conditional graph edges for multi-path orchestration
4. Clear audit logging for execution tracing
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Literal, Any, Dict
from dataclasses import dataclass

from pydantic import BaseModel, Field, ConfigDict
from langgraph.graph import StateGraph, END
from langgraph.types import Send
from typing_extensions import TypedDict, Annotated

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("corporate-intelligence-engine")


# ============================================================================
# STATE MODEL - PYDANTIC BASEMODEL
# ============================================================================

class AgentState(BaseModel):
    """Central state tracking all execution context through the graph."""
    
    model_config = ConfigDict(extra="allow")
    
    user_input: str = Field(
        description="The original user query or request"
    )
    current_target_ticker: str = Field(
        default="", 
        description="Stock ticker extracted by the router (e.g., 'NVDA', 'TSLA')"
    )
    routing_decision: str = Field(
        default="",
        description="Routing decision: 'research', 'general_q', or 'error'"
    )
    research_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Collected financial/research data"
    )
    report_markdown: str = Field(
        default="",
        description="Final formatted report in Markdown"
    )
    error_count: int = Field(
        default=0,
        description="Count of errors encountered during execution"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="When this state was created"
    )


class RouterDecision(BaseModel):
    """Structured output from the Triage/Router LLM."""
    
    ticker: str = Field(
        description="Extracted stock ticker symbol (e.g., 'NVDA')"
    )
    routing_path: Literal["research", "general_q"] = Field(
        description="Next node: 'research' for ticker analysis, 'general_q' for other queries"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score of the routing decision (0.0-1.0)"
    )
    reasoning: str = Field(
        description="Brief explanation of the routing decision"
    )


# ============================================================================
# GRAPH STATE TYPEDDICT (Required by LangGraph)
# ============================================================================

class GraphState(TypedDict, total=False):
    """Type definition for the state graph edges."""
    user_input: str
    current_target_ticker: str
    routing_decision: str
    research_data: Dict[str, Any]
    report_markdown: str
    error_count: int


# ============================================================================
# LLM ROUTING - TRIAGE NODE
# ============================================================================

def triage_node(state: GraphState) -> GraphState:
    """
    Triage/Router Node - Analyzes user input and extracts actionable information.
    
    This node:
    1. Takes the raw user input
    2. Uses LLM (mocked here) with structured output to parse the request
    3. Extracts stock ticker if present
    4. Decides the next routing path (research vs general_q)
    5. Returns updated state for conditional routing
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with routing_decision and current_target_ticker
    """
    logger.info("=" * 80)
    logger.info("[ENTERING TRIAGE NODE]")
    logger.info(f"User Input: {state['user_input']}")
    logger.info("-" * 80)
    
    # ────────────────────────────────────────────────────────────────────
    # MOCK LLM CALL - In production, use OpenAI/Anthropic structured output
    # ────────────────────────────────────────────────────────────────────
    
    logger.info("Invoking LLM for structured routing decision...")
    
    # Simulate LLM inference with rule-based fallback
    user_input_upper = state["user_input"].upper()
    
    # Simple heuristic extraction (in production, use proper NLP/LLM)
    mock_routing_decision = mock_extract_routing_decision(user_input_upper)
    
    logger.info(f"LLM Response: {json.dumps(mock_routing_decision.model_dump(), indent=2)}")
    
    # ────────────────────────────────────────────────────────────────────
    # UPDATE STATE
    # ────────────────────────────────────────────────────────────────────
    
    state["current_target_ticker"] = mock_routing_decision.ticker
    state["routing_decision"] = mock_routing_decision.routing_path
    
    logger.info(f"Extracted Ticker: {mock_routing_decision.ticker}")
    logger.info(f"Routing Decision: {mock_routing_decision.routing_path}")
    logger.info(f"Confidence: {mock_routing_decision.confidence:.2%}")
    logger.info("[TRIAGE NODE COMPLETE]")
    logger.info("=" * 80)
    
    return state


def mock_extract_routing_decision(user_input: str) -> RouterDecision:
    """
    Mock LLM that extracts routing decision using simple heuristics.
    
    In a production system, this would call an actual LLM (e.g., GPT-4) with
    a structured output schema. For the walking skeleton, we use pattern matching.
    """
    
    # List of common financial keywords
    financial_keywords = [
        "EARNINGS", "STOCK", "TICKER", "PRICE", "ANALYZE", 
        "FORECAST", "REVENUE", "PE RATIO", "DIVIDEND"
    ]
    
    is_financial_query = any(kw in user_input for kw in financial_keywords)
    
    # Simple ticker extraction (look for patterns like NVDA, TSLA, AAPL)
    import re
    ticker_pattern = r"\b([A-Z]{1,5})\b"
    matches = re.findall(ticker_pattern, user_input)
    
    # Filter for likely tickers (1-5 uppercase letters)
    ticker = matches[0] if matches else "UNKNOWN"
    
    # Routing logic
    if is_financial_query and ticker != "UNKNOWN":
        routing_path = "research"
        confidence = 0.92
        reasoning = f"Financial query detected with ticker '{ticker}' mentioned"
    elif is_financial_query:
        routing_path = "research"
        confidence = 0.75
        reasoning = "Financial query detected, but no specific ticker provided"
    else:
        routing_path = "general_q"
        ticker = ""
        confidence = 0.85
        reasoning = "General question not related to specific stock research"
    
    return RouterDecision(
        ticker=ticker,
        routing_path=routing_path,
        confidence=confidence,
        reasoning=reasoning,
    )


# ============================================================================
# RESEARCH NODE - STUB
# ============================================================================

def research_node(state: GraphState) -> GraphState:
    """
    Research Node - Gathers and synthesizes financial research data.
    
    This stub demonstrates the research workflow:
    1. Accepts routed state with ticker
    2. Simulates data gathering from multiple sources
    3. Appends mock financial data to state
    4. Returns enriched state for reporting
    
    Args:
        state: Current graph state with ticker set
        
    Returns:
        State with research_data populated
    """
    logger.info("=" * 80)
    logger.info("[ENTERING RESEARCH NODE]")
    logger.info(f"Target Ticker: {state['current_target_ticker']}")
    logger.info("-" * 80)
    
    ticker = state["current_target_ticker"]
    
    if not ticker or ticker == "UNKNOWN":
        logger.warning("No valid ticker provided to research node")
        state["error_count"] += 1
        state["research_data"] = {"error": "No ticker provided"}
        logger.info("[RESEARCH NODE COMPLETE - ERROR]")
        logger.info("=" * 80)
        return state
    
    # ────────────────────────────────────────────────────────────────────
    # MOCK DATA GATHERING - In production, call real financial APIs
    # ────────────────────────────────────────────────────────────────────
    
    logger.info(f"Simulating data gathering for {ticker}...")
    
    # Mock financial data for this ticker
    mock_financial_data = {
        "ticker": ticker,
        "company_name": f"Mock Company for {ticker}",
        "current_price": 150.25,
        "market_cap_b": 2500.0,  # in billions
        "pe_ratio": 28.5,
        "revenue_ttm_b": 85.0,
        "net_income_ttm_b": 15.2,
        "year_high": 165.50,
        "year_low": 95.30,
        "52week_change_pct": 52.1,
        "analyst_rating": "BUY",
        "target_price": 175.00,
        "sectors": ["Technology", "Semiconductor"],
        "recent_events": [
            "Q3 2024 earnings beat expectations",
            "New AI chip announced",
            "Partnership with major cloud provider"
        ],
    }
    
    logger.info(f"Retrieved data: {json.dumps(mock_financial_data, indent=2)}")
    
    # Simulate additional processing/validation
    logger.info("Validating data integrity...")
    logger.info("Enriching with sentiment analysis...")
    
    state["research_data"] = mock_financial_data
    
    logger.info(f"Research complete. {len(mock_financial_data)} data points collected.")
    logger.info("[RESEARCH NODE COMPLETE]")
    logger.info("=" * 80)
    
    return state


# ============================================================================
# GENERAL Q NODE - STUB
# ============================================================================

def general_q_node(state: GraphState) -> GraphState:
    """
    General Question Node - Handles non-research queries.
    
    This stub demonstrates handling of general inquiries:
    1. Accepts routed state
    2. Processes general query (could involve QA model, knowledge base, etc.)
    3. Generates response
    4. Returns enriched state with report
    
    Args:
        state: Current graph state
        
    Returns:
        State with report_markdown populated
    """
    logger.info("=" * 80)
    logger.info("[ENTERING GENERAL Q NODE]")
    logger.info(f"Query: {state['user_input']}")
    logger.info("-" * 80)
    
    # ────────────────────────────────────────────────────────────────────
    # MOCK GENERAL QUESTION HANDLING
    # ────────────────────────────────────────────────────────────────────
    
    logger.info("Processing general inquiry...")
    logger.info("Consulting knowledge base...")
    
    mock_response = f"""
# Response to General Query

**Question:** {state['user_input']}

**Answer:**
This is a mock response from the General Q node. In a production system, this would:
- Search a knowledge base
- Use a QA model to generate contextual answers
- Provide citations and sources
- Handle follow-up questions

**Generated at:** {datetime.now().isoformat()}

---
*This is a walking skeleton demonstrating the orchestration flow.*
""".strip()
    
    state["report_markdown"] = mock_response
    
    logger.info("General query processed successfully")
    logger.info("[GENERAL Q NODE COMPLETE]")
    logger.info("=" * 80)
    
    return state


# ============================================================================
# REPORTING NODE - FINAL STEP
# ============================================================================

def reporting_node(state: GraphState) -> GraphState:
    """
    Reporting Node - Consolidates findings into a final report.
    
    This node:
    1. Takes processed state (from either research or general_q)
    2. Formats the final output
    3. Adds metadata
    4. Returns completed state
    
    Args:
        state: Current graph state
        
    Returns:
        State with complete report_markdown
    """
    logger.info("=" * 80)
    logger.info("[ENTERING REPORTING NODE]")
    logger.info("-" * 80)
    
    if state.get("research_data") and state["current_target_ticker"]:
        # Research path
        ticker = state["current_target_ticker"]
        data = state["research_data"]
        
        if "error" in data:
            report = f"### Error Processing {ticker}\n\n{data['error']}"
        else:
            report = f"""# Financial Research Report: {ticker}

## Company Overview
- **Company:** {data.get('company_name', 'N/A')}
- **Current Price:** ${data.get('current_price', 'N/A')}
- **Market Cap:** ${data.get('market_cap_b', 'N/A')}B

## Key Metrics
- **P/E Ratio:** {data.get('pe_ratio', 'N/A')}
- **Revenue (TTM):** ${data.get('revenue_ttm_b', 'N/A')}B
- **Net Income (TTM):** ${data.get('net_income_ttm_b', 'N/A')}B
- **52-Week Change:** {data.get('52week_change_pct', 'N/A')}%

## Valuation
- **52-Week Range:** ${data.get('year_low', 'N/A')} - ${data.get('year_high', 'N/A')}
- **Analyst Rating:** {data.get('analyst_rating', 'N/A')}
- **Price Target:** ${data.get('target_price', 'N/A')}

## Recent Events
"""
            for event in data.get('recent_events', []):
                report += f"- {event}\n"
        
        state["report_markdown"] = report
    
    logger.info("Report generation complete")
    logger.info("[REPORTING NODE COMPLETE]")
    logger.info("=" * 80)
    
    return state


# ============================================================================
# CONDITIONAL ROUTING LOGIC
# ============================================================================

def route_after_triage(state: GraphState) -> str:
    """
    Conditional router that determines the next node based on routing_decision.
    
    This function is called after the Triage Node and reads state["routing_decision"]
    to determine which downstream node to invoke:
    - "research" -> research_node
    - "general_q" -> general_q_node
    
    Args:
        state: Current graph state
        
    Returns:
        Name of the next node to execute
    """
    logger.info(f"[CONDITIONAL ROUTING] Decision: {state['routing_decision']}")
    
    decision = state.get("routing_decision", "general_q")
    
    if decision == "research":
        logger.info("[CONDITIONAL EDGE] Taking RESEARCH path")
        return "research"
    else:
        logger.info("[CONDITIONAL EDGE] Taking GENERAL_Q path")
        return "general_q"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def build_graph() -> StateGraph:
    """
    Constructs the LangGraph state graph with all nodes and conditional edges.
    
    Graph structure:
    ```
    triage_node (START)
        |
        +-- route_after_triage (conditional)
        |
        +-> research_node --+
        |                    |
        +-> general_q_node --+
        |                    |
        +-- reporting_node (END)
    ```
    
    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info("\n" + "=" * 80)
    logger.info("BUILDING STATE GRAPH")
    logger.info("=" * 80)
    
    # Create graph with GraphState
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("triage", triage_node)
    graph.add_node("research", research_node)
    graph.add_node("general_q", general_q_node)
    graph.add_node("reporting", reporting_node)
    
    logger.info("✓ Nodes added: triage, research, general_q, reporting")
    
    # Define entry point
    graph.set_entry_point("triage")
    logger.info("✓ Entry point: triage")
    
    # Add conditional edge from triage
    graph.add_conditional_edges(
        source="triage",
        path=route_after_triage,
        path_map={
            "research": "research",
            "general_q": "general_q",
        },
    )
    logger.info("✓ Conditional edge added: triage -> (research | general_q)")
    
    # Connect research and general_q to reporting
    graph.add_edge("research", "reporting")
    graph.add_edge("general_q", "reporting")
    logger.info("✓ Edges added: research -> reporting, general_q -> reporting")
    
    # End state
    graph.add_edge("reporting", END)
    logger.info("✓ Edge added: reporting -> END")
    
    logger.info("=" * 80)
    logger.info("GRAPH COMPILATION COMPLETE")
    logger.info("=" * 80 + "\n")
    
    # Compile the graph
    compiled_graph = graph.compile()
    
    return compiled_graph


# ============================================================================
# EXECUTION HELPERS
# ============================================================================

def execute_graph(graph: StateGraph, user_input: str) -> GraphState:
    """
    Executes the compiled graph with the given user input.
    
    Args:
        graph: Compiled StateGraph
        user_input: User query string
        
    Returns:
        Final state after full execution
    """
    logger.info(f"\n{'#' * 80}")
    logger.info(f"# GRAPH EXECUTION - User Query")
    logger.info(f"{'#' * 80}")
    logger.info(f"Input: {user_input}\n")
    
    # Initialize state
    initial_state: GraphState = {
        "user_input": user_input,
        "current_target_ticker": "",
        "routing_decision": "",
        "research_data": {},
        "report_markdown": "",
        "error_count": 0,
    }
    
    # Execute
    final_state = graph.invoke(initial_state)
    
    logger.info(f"\n{'#' * 80}")
    logger.info(f"# GRAPH EXECUTION - COMPLETE")
    logger.info(f"{'#' * 80}\n")
    
    return final_state


def print_final_report(state: GraphState) -> None:
    """Pretty-prints the final state and report."""
    logger.info("\n" + "=" * 80)
    logger.info("FINAL STATE SUMMARY")
    logger.info("=" * 80)
    logger.info(f"User Input: {state['user_input']}")
    logger.info(f"Target Ticker: {state['current_target_ticker']}")
    logger.info(f"Routing Decision: {state['routing_decision']}")
    logger.info(f"Errors Encountered: {state['error_count']}")
    logger.info(f"Research Data Keys: {list(state.get('research_data', {}).keys())}")
    logger.info("=" * 80)
    
    if state.get("report_markdown"):
        logger.info("\n" + "=" * 80)
        logger.info("FINAL REPORT")
        logger.info("=" * 80)
        print("\n" + state["report_markdown"] + "\n")
        logger.info("=" * 80 + "\n")


# ============================================================================
# MAIN EXECUTION - TEST CASES
# ============================================================================

if __name__ == "__main__":
    logger.info("\n\n")
    logger.info("╔" + "═" * 78 + "╗")
    logger.info("║" + " " * 78 + "║")
    logger.info("║" + "  CORPORATE INTELLIGENCE ENGINE - WALKING SKELETON  ".center(78) + "║")
    logger.info("║" + "  AI State Graph with LangGraph & Pydantic  ".center(78) + "║")
    logger.info("║" + " " * 78 + "║")
    logger.info("╚" + "═" * 78 + "╝")
    logger.info("\n")
    
    # Build the graph once
    graph = build_graph()
    
    # Test cases demonstrating different routing paths
    test_queries = [
        # Test 1: Research query with specific ticker
        "Analyze the latest earnings for NVDA",
        
        # Test 2: Research query without explicit ticker
        "Show me the forecast for Tesla stock revenue",
        
        # Test 3: General question (non-research)
        "What are the top machine learning frameworks in 2024?",
    ]
    
    logger.info("\n" + "▼" * 80)
    logger.info("EXECUTING TEST CASES")
    logger.info("▼" * 80 + "\n")
    
    for idx, query in enumerate(test_queries, 1):
        logger.info(f"\n{'─' * 80}")
        logger.info(f"TEST CASE {idx}/{len(test_queries)}")
        logger.info(f"{'─' * 80}\n")
        
        final_state = execute_graph(graph, query)
        print_final_report(final_state)
        
        logger.info("\n")
    
    logger.info("\n" + "▲" * 80)
    logger.info("ALL TEST CASES COMPLETE")
    logger.info("▲" * 80 + "\n")
