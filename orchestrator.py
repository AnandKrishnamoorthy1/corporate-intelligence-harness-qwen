"""
Corporate Intelligence Engine — Agentic AI Orchestrator

A production-grade LangGraph state machine that orchestrates a multi-agent
financial research and autonomous trading workflow:

1. Pydantic-based immutable state management
2. Qwen-powered triage with structured JSON routing output
3. Tri-Agent Adversarial Investment Committee (Bull / Bear / Director)
4. 4-path conditional graph routing: research | direct_trade | portfolio | general_q
5. Human-in-loop approval checkpoints before any trade execution
6. Robinhood Agentic Trading MCP integration with paper-trading fallback
7. Full audit logging via loguru for every execution step

LLM: Alibaba Qwen (qwen3.7-plus) via DashScope international endpoint.
External data: Alpha Vantage (real-time quote + fundamentals) + SEC EDGAR 10-Q (XBRL).
"""

import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Literal, Any, Dict
from dataclasses import dataclass

from loguru import logger
from pydantic import BaseModel, Field, ConfigDict
from langgraph.graph import StateGraph, END
from langgraph.types import Send
from typing_extensions import TypedDict, Annotated

from app.llm import call_qwen_for_triage, call_qwen_for_research, call_qwen_for_general_qa
from app.agents import run_investment_committee
from app.tools import financial_tools
from app.trading import RobinhoodMCPClient, OrderSide, OrderType

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Configure loguru with custom format
logger.remove()  # Remove default handler
logger.add(
    lambda msg: print(msg, end=""),
    format="<level>{time:YYYY-MM-DD HH:mm:ss}</level> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
)


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
    routing_path: Literal["research", "general_q", "direct_trade", "portfolio"] = Field(
        description="Next node: 'research' for analysis, 'direct_trade' for immediate trade, 'general_q' for other queries, 'portfolio' for portfolio review"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score of the routing decision (0.0-1.0)"
    )
    reasoning: str = Field(
        description="Brief explanation of the routing decision"
    )
    trade_action: str = Field(
        default="",
        description="For direct_trade path: BUY or SELL action and quantity"
    )


# ============================================================================
# APPROVAL/CHECKPOINT MODELS - FOR HUMAN-IN-LOOP
# ============================================================================

class ApprovalRequest(BaseModel):
    """Request requiring human approval - human-in-loop checkpoint."""
    
    request_id: str = Field(
        description="Unique identifier for this approval request"
    )
    action: str = Field(
        description="Recommended action: BUY, SELL, HOLD, etc."
    )
    ticker: str = Field(
        description="Stock ticker symbol"
    )
    reasoning: str = Field(
        description="Qwen's reasoning for the recommendation"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score of the recommendation"
    )
    timestamp: str = Field(
        description="When the approval request was created"
    )


class ApprovalResponse(BaseModel):
    """Human's approval/rejection decision."""
    
    approved: bool = Field(
        description="Whether human approved the recommendation"
    )
    approver_notes: str = Field(
        default="",
        description="Human's notes/reasoning for approval or rejection"
    )


# ============================================================================
# GRAPH STATE TYPEDDICT (Required by LangGraph)
# ============================================================================

class GraphState(TypedDict, total=False):
    """Type definition for the state graph edges."""
    user_input: str
    current_target_ticker: str
    routing_decision: str
    trade_action: str  # "BUY" or "SELL" for direct trades
    research_data: Dict[str, Any]
    report_markdown: str
    error_count: int
    pending_approval: Dict[str, Any]  # Approval request waiting for human
    approval_status: str  # "pending", "approved", "rejected"


# ============================================================================
# LLM ROUTING - TRIAGE NODE
# ============================================================================

def triage_node(state: GraphState) -> GraphState:
    """
    Triage/Router Node - Uses Qwen to analyze and route user input.
    
    This node:
    1. Takes the raw user input
    2. Uses Qwen LLM with structured output to parse the request
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
    # QWEN LLM CALL - Structured output for routing decision
    # ────────────────────────────────────────────────────────────────────
    
    logger.info("Invoking Qwen LLM for structured routing decision...")
    
    try:
        qwen_routing_decision = call_qwen_for_triage(state["user_input"])
        logger.info(f"Qwen Response: {json.dumps(qwen_routing_decision, indent=2)}")
        
        # ────────────────────────────────────────────────────────────────────
        # UPDATE STATE WITH QWEN RESPONSE
        # ────────────────────────────────────────────────────────────────────
        
        state["current_target_ticker"] = qwen_routing_decision.get("ticker", "")
        state["routing_decision"] = qwen_routing_decision.get("routing_path", "general_q")
        
        confidence = qwen_routing_decision.get("confidence", 0.0)
        reasoning = qwen_routing_decision.get("reasoning", "No reasoning provided")
        trade_action = qwen_routing_decision.get("trade_action", None)
        
        logger.info(f"Extracted Ticker: {state['current_target_ticker']}")
        logger.info(f"Routing Decision: {state['routing_decision']}")
        logger.info(f"Confidence: {confidence:.2%}")
        logger.info(f"Reasoning: {reasoning}")
        if trade_action:
            logger.info(f"Trade Action: {trade_action}")
            state['trade_action'] = trade_action  # Set at root level
        
        # Store trade action for direct_trade path
        if state['routing_decision'] == 'direct_trade' and trade_action:
            state['pending_approval'] = {
                'ticker': state['current_target_ticker'],
                'action': trade_action,
                'routing': state['routing_decision'],
                'user_input': state['user_input'],
            }
        
    except Exception as e:
        logger.error(f"Qwen triage call failed: {str(e)}")
        logger.warning("Falling back to general Q&A path")
        state["routing_decision"] = "general_q"
        state["current_target_ticker"] = ""
        state["error_count"] += 1
    
    logger.info("[TRIAGE NODE COMPLETE]")
    logger.info("=" * 80)
    
    return state


# ============================================================================
# RESEARCH NODE - STUB
# ============================================================================

def research_node(state: GraphState) -> GraphState:
    """
    Research Node - Uses Qwen to generate financial research analysis with human approval.
    
    This node:
    1. Accepts routed state with ticker
    2. Calls REAL Alpha Vantage API for live financial data
    3. Uses Qwen to generate comprehensive AI analysis
    4. Adds human-in-loop approval checkpoint for BUY/SELL recommendations
    5. Returns state with analysis and approval request (if needed)
    
    This demonstrates:
    - External tool invocation (Alpha Vantage API)
    - Human-in-loop checkpoints at critical decision points
    - Production-ready error handling
    
    Args:
        state: Current graph state with ticker set
        
    Returns:
        State with research_data, report_markdown, and optional pending_approval
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
    # EXTERNAL TOOL: ALPHA VANTAGE API - REAL DATA
    # ────────────────────────────────────────────────────────────────────
    
    logger.info("[EXTERNAL TOOL] Calling Alpha Vantage API for real stock data + fundamentals...")
    
    # Quote and OVERVIEW fetched in parallel inside get_enriched_stock_data
    real_stock_data = financial_tools.get_enriched_stock_data(ticker)
    
    logger.info(f"[EXTERNAL TOOL RESULT] {real_stock_data['data_source']}")
    logger.info(f"  Price: ${real_stock_data['price']}")
    logger.info(f"  Change: {real_stock_data['change_percent']:+.2f}%")
    logger.info(f"  Volume: {real_stock_data['volume']:,}")
    if real_stock_data.get("sector"):
        logger.info(f"  Sector: {real_stock_data['sector']}")
    if real_stock_data.get("pe_ratio"):
        logger.info(f"  P/E Ratio: {real_stock_data['pe_ratio']}")
    if real_stock_data.get("eps"):
        logger.info(f"  EPS: ${real_stock_data['eps']}")
    if real_stock_data.get("analyst_target_price"):
        logger.info(f"  Analyst Target: ${real_stock_data['analyst_target_price']}")
    sec = real_stock_data.get("sec_filings", {})
    if sec.get("available"):
        logger.info(f"  SEC Filings: {len(sec.get('quarters', []))} quarters loaded")
    else:
        logger.info(f"  SEC Filings: unavailable ({sec.get('reason', 'unknown')})") 
    
    # ────────────────────────────────────────────────────────────────────
    # MULTI-AGENT ANALYSIS: TRI-AGENT ADVERSARIAL INVESTMENT COMMITTEE
    # Bull Analyst vs Bear Auditor, moderated by the Portfolio Director.
    # ────────────────────────────────────────────────────────────────────

    try:
        logger.info("Convening Tri-Agent Investment Committee on REAL data...")

        committee_result = run_investment_committee(
            ticker=ticker,
            market_data=real_stock_data,
            rounds=2,
        )

        verdict = committee_result["verdict"]
        report_markdown = committee_result["report_markdown"]

        state["research_data"] = {
            **real_stock_data,
            "committee_verdict": verdict,
            "committee_transcript": committee_result["transcript"],
        }
        state["report_markdown"] = report_markdown

        recommendation = verdict.get("verdict", "HOLD")
        committee_confidence = float(verdict.get("confidence", 0.0))

        logger.info(
            f"Committee reached verdict: {recommendation} "
            f"({committee_confidence:.0%} confidence)"
        )

        # ────────────────────────────────────────────────────────────────────
        # HUMAN-IN-LOOP CHECKPOINT
        # If the committee recommends BUY/SELL, require human approval
        # ────────────────────────────────────────────────────────────────────

        if recommendation in ["BUY", "SELL"]:
            logger.warning("[CHECKPOINT] Committee verdict requires human approval!")
            logger.warning(f"[CHECKPOINT] Action: {recommendation}")

            request_id = f"{ticker}-{datetime.now().timestamp()}"

            approval_request = ApprovalRequest(
                request_id=request_id,
                action=recommendation,
                ticker=ticker,
                reasoning=(
                    f"Investment Committee ({recommendation}): "
                    f"{verdict.get('thesis', '')}"
                ),
                confidence=committee_confidence,
                timestamp=datetime.now().isoformat(),
            )

            state["pending_approval"] = approval_request.model_dump()
            state["approval_status"] = "pending"
            state["routing_decision"] = "awaiting_approval"

            logger.warning(f"[CHECKPOINT] Approval request {request_id} created")
            logger.warning("[CHECKPOINT] Workflow PAUSED - awaiting human decision")
            logger.info("[RESEARCH NODE COMPLETE - AWAITING APPROVAL]")

        else:
            # HOLD or other recommendation - no approval needed
            logger.info(f"[NO CHECKPOINT] Committee verdict: {recommendation} (no approval needed)")
            state["routing_decision"] = "completed"
            logger.info("[RESEARCH NODE COMPLETE]")

        logger.info("=" * 80)
        return state

    except Exception as e:
        logger.error(f"Investment committee analysis failed: {str(e)}")
        logger.warning("Using fallback research data format")
        state["research_data"] = real_stock_data
        state["error_count"] += 1
        
        # Fallback report
        state["report_markdown"] = f"""# Financial Research Report: {ticker}

## Live Market Data (Real Alpha Vantage)
- **Current Price:** ${real_stock_data['price']}
- **Change:** {real_stock_data['change_percent']:+.2f}%
- **Volume:** {real_stock_data['volume']:,}
- **Data Source:** {real_stock_data['data_source']}

## Analysis Status
*Detailed Qwen analysis generation failed. Please check Qwen API connection.*

---
*Generated at: {datetime.now().isoformat()}*
"""
        state["routing_decision"] = "completed"
        logger.info("[RESEARCH NODE COMPLETE - ERROR]")
        logger.info("=" * 80)
        return state


def _extract_recommendation(report_markdown: str) -> str:
    """
    Extract recommendation from Qwen report.
    
    Looks for keywords: BUY, SELL, HOLD, etc.
    Falls back to HOLD if unclear.
    """
    report_upper = report_markdown.upper()
    
    if "BUY" in report_upper:
        return "BUY"
    elif "SELL" in report_upper:
        return "SELL"
    elif "HOLD" in report_upper:
        return "HOLD"
    else:
        return "HOLD"  # Safe default


# ============================================================================
# GENERAL Q NODE - STUB
# ============================================================================

def general_q_node(state: GraphState) -> GraphState:
    """
    General Question Node - Uses Qwen to handle non-research queries.
    
    This node:
    1. Accepts routed state
    2. Uses Qwen to process general financial inquiries
    3. Generates comprehensive answer
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
    # QWEN GENERAL Q&A
    # ────────────────────────────────────────────────────────────────────
    
    try:
        logger.info("Invoking Qwen for general Q&A...")
        
        answer = call_qwen_for_general_qa(state["user_input"])
        state["report_markdown"] = answer
        
        logger.info(f"General Q&A response generated ({len(answer)} chars)")
        
    except Exception as e:
        logger.error(f"Qwen QA call failed: {str(e)}")
        logger.warning("Using fallback response format")
        state["error_count"] += 1
        
        # Fallback response
        state["report_markdown"] = f"""# Response to Your Question

**Question:** {state['user_input']}

**Answer:**
I encountered an issue retrieving a detailed response at this moment. 
Please check your Qwen API connection and try again.

**Tips:**
- Ensure QWEN_API_KEY environment variable is set
- Verify your Qwen API key has available credits
- Check your internet connection

---
*Generated at: {datetime.now().isoformat()}*
"""
    
    logger.info("General query processed")
    logger.info("[GENERAL Q NODE COMPLETE]")
    logger.info("=" * 80)
    
    return state


# ============================================================================
# TRADING NODE - DIRECT TRADE EXECUTION
# ============================================================================

def trading_node(state: GraphState) -> GraphState:
    """
    Trading Node - Processes direct trade requests with Robinhood integration.
    
    This node:
    1. Accepts routed state with trade action (BUY/SELL)
    2. Extracts dollar amount from user input
    3. Creates a human-in-loop approval request
    4. WAITS for human approval before executing
    5. Returns state with pending_approval for checkpoint
    
    This is crucial for safe agentic trading - NO TRADE is executed without approval!
    
    Args:
        state: Current graph state with trade action
        
    Returns:
        State with pending_approval and approval_status="pending"
    """
    import re
    
    logger.info("=" * 80)
    logger.info("[ENTERING TRADING NODE]")
    logger.info(f"Target Ticker: {state['current_target_ticker']}")
    logger.info(f"Trade Action: {state.get('trade_action', 'N/A')}")
    logger.info("-" * 80)
    
    ticker = state.get("current_target_ticker", "")
    trade_action = state.get("trade_action", "").upper()  # "BUY" or "SELL"
    user_input = state.get("user_input", "")
    
    if not ticker or not trade_action:
        logger.error("Invalid trade parameters")
        state["error_count"] += 1
        state["routing_decision"] = "completed"
        return state
    
    if trade_action not in ["BUY", "SELL"]:
        logger.error(f"Invalid trade action: {trade_action}")
        state["error_count"] += 1
        state["routing_decision"] = "completed"
        return state
    
    # ────────────────────────────────────────────────────────────────────
    # Extract dollar amount from user input
    # ────────────────────────────────────────────────────────────────────
    
    # Look for patterns like "$5", "$2", "$100.50"
    dollar_pattern = r'\$([0-9]+(?:\.[0-9]{2})?)'
    match = re.search(dollar_pattern, user_input)
    
    amount_dollars = None
    quantity = None
    
    if match:
        try:
            amount_dollars = float(match.group(1))
            logger.info(f"Extracted dollar amount: ${amount_dollars:.2f}")
        except ValueError:
            logger.warning(f"Could not parse dollar amount from: {match.group(0)}")
    else:
        # Look for quantity patterns like "10 shares", "5 shares of", "buy 10"
        quantity_pattern = r'(\d+(?:\.\d+)?)\s*(?:shares?)?'
        qty_match = re.search(quantity_pattern, user_input)
        if qty_match:
            try:
                quantity = float(qty_match.group(1))
                logger.info(f"Extracted quantity: {quantity} shares")
            except ValueError:
                logger.warning(f"Could not parse quantity from: {qty_match.group(0)}")
    
    if not amount_dollars and not quantity:
        logger.error(f"Could not extract dollar amount or quantity from: {user_input}")
        state["error_count"] += 1
        state["routing_decision"] = "completed"
        return state
    
    try:
        # ────────────────────────────────────────────────────────────────────
        # CREATE HUMAN APPROVAL REQUEST
        # ────────────────────────────────────────────────────────────────────
        
        request_id = f"{ticker}-{trade_action}-{datetime.now().timestamp()}"
        
        # Build reasoning with extracted amount
        if amount_dollars:
            reasoning_detail = f"Dollar-based trade: {trade_action} ${amount_dollars:.2f} of {ticker}"
            formatted_amount = f"${amount_dollars:.2f}"
        else:
            reasoning_detail = f"Share-based trade: {trade_action} {quantity} shares of {ticker}"
            formatted_amount = f"{quantity} shares"
        
        approval_request = ApprovalRequest(
            request_id=request_id,
            action=trade_action,
            ticker=ticker,
            reasoning=f"Direct trade request: {reasoning_detail}\n"
                     f"User query: {user_input}",
            confidence=0.95,
            timestamp=datetime.now().isoformat(),
        )
        
        state["pending_approval"] = {
            **approval_request.model_dump(),
            "amount": formatted_amount,
            "amount_dollars": amount_dollars,
            "quantity": quantity,
            "order_type": "market",
        }
        state["approval_status"] = "pending"
        state["routing_decision"] = "awaiting_approval"
        
        logger.warning("[CHECKPOINT] Trade requires human approval!")
        logger.warning(f"[CHECKPOINT] Approval request {request_id} created")
        logger.warning(f"[CHECKPOINT] Action: {trade_action} {ticker}")
        if amount_dollars:
            logger.warning(f"[CHECKPOINT] Amount: ${amount_dollars:.2f}")
        else:
            logger.warning(f"[CHECKPOINT] Quantity: {quantity} shares")
        logger.warning("[CHECKPOINT] Workflow PAUSED - awaiting human decision")
        
        # Generate pending report
        state["report_markdown"] = f"""# Pending Trade Approval

## Trade Details
- **Action:** {trade_action}
- **Ticker:** {ticker}
- **Amount:** ${amount_dollars:.2f}
- **Type:** Market Order
- **Status:** ⏳ AWAITING HUMAN APPROVAL

## User Request
{user_input}

## ⚠️ Important
This trade requires your explicit approval before execution. Please review the details above.
To approve or reject, use the approval endpoint or web interface.

---
*Trade request created at: {datetime.now().isoformat()}*
*Request ID: {request_id}*
"""
        
        logger.info("[TRADING NODE COMPLETE - AWAITING APPROVAL]")
        
    except Exception as e:
        logger.error(f"Trade parsing failed: {str(e)}")
        state["error_count"] += 1
        state["routing_decision"] = "completed"
        state["report_markdown"] = f"Trade execution failed: {str(e)}"
        logger.info("[TRADING NODE COMPLETE - ERROR]")
    
    logger.info("=" * 80)
    return state


# ============================================================================
# APPROVAL EXECUTION NODE - EXECUTES APPROVED TRADES
# ============================================================================

def approval_execution_node(state: GraphState) -> GraphState:
    """
    Approval Execution Node - Executes trades after human approval.
    
    This node:
    1. Checks if approval_status is "approved"
    2. Calls Robinhood MCP to execute the trade
    3. Generates execution report with order details
    4. Handles execution errors gracefully
    
    This node runs ONLY if:
    - pending_approval exists
    - approval_status == "approved"
    
    Args:
        state: Current graph state with pending_approval
        
    Returns:
        State with execution results
    """
    logger.info("=" * 80)
    logger.info("[ENTERING APPROVAL EXECUTION NODE]")
    logger.info("-" * 80)
    
    if state.get("approval_status") != "approved":
        # IMPORTANT: Do NOT overwrite the report here unless a trade was
        # *explicitly rejected*. During the initial graph run, a research query
        # legitimately ends with approval_status == None (HOLD verdict) or
        # "pending" (BUY/SELL awaiting a human). In those cases the committee
        # report is already in state["report_markdown"] and must be preserved.
        if state.get("approval_status") == "rejected":
            logger.warning("[SKIPPING] Trade was rejected by the human approver.")
            state["report_markdown"] = """# Trade Cancelled

## Status
The pending trade was **REJECTED** by the human approver.

No trade was executed.
"""
            logger.info("[APPROVAL EXECUTION NODE COMPLETE - REJECTED]")
        else:
            logger.info(
                "[APPROVAL EXECUTION NODE] No approved trade to execute "
                f"(approval_status={state.get('approval_status')!r}); "
                "preserving existing report."
            )
            logger.info("[APPROVAL EXECUTION NODE COMPLETE - NO EXECUTION]")
        logger.info("=" * 80)
        return state
    
    try:
        pending = state.get("pending_approval", {})
        ticker = pending.get("ticker", "")
        action = pending.get("action", "")
        amount_dollars = pending.get("amount_dollars")
        quantity = pending.get("quantity")
        
        if amount_dollars:
            logger.info(f"Executing approved trade: {action} ${amount_dollars:.2f} of {ticker}")
            trade_detail = f"${amount_dollars:.2f}"
        else:
            logger.info(f"Executing approved trade: {action} {quantity} shares of {ticker}")
            trade_detail = f"{quantity} shares"
        
        # ────────────────────────────────────────────────────────────────────
        # BROKER EXECUTION — routes through BrokerFactory (simulation or live)
        # ────────────────────────────────────────────────────────────────────

        from app.trading import get_broker_for_user, get_account_id_for_user
        from app.trading.broker_interface import OrderSide as BS

        broker = get_broker_for_user()
        account_id = get_account_id_for_user()

        logger.info(f"[BROKER] Submitting {action} order via {type(broker).__name__}...")
        logger.info(f"[BROKER] Ticker: {ticker}  |  Amount: {trade_detail}")

        side = BS.BUY if action.upper() == "BUY" else BS.SELL
        order = asyncio.run(
            broker.place_order(
                account_id=account_id,
                ticker=ticker,
                side=side,
                amount_dollars=amount_dollars,
                quantity=quantity,
            )
        )

        order_id = order.order_id
        status_emoji = "✅" if order.status in ("filled", "submitted") else "❌"
        filled_price_str = (
            f"\\${order.filled_price:.2f}" if order.filled_price else "market"
        )
        filled_qty = f"{order.quantity:.4f}" if order.quantity else "?"
        total_val = f"\\${order.total_value:,.2f}" if order.total_value else trade_detail
        simulated_note = (
            "Paper-trading simulation (real Alpha Vantage price, simulated balance)"
            if getattr(order, "simulated", True)
            else "Live order via Robinhood MCP"
        )

        execution_report = f"""# Trade Execution Report

## {status_emoji} Trade {"Executed" if order.status in ("filled", "submitted") else "Failed"}

### Order Details
| Field | Value |
|---|---|
| **Order ID** | `{order_id}` |
| **Ticker** | {ticker} |
| **Action** | {action} |
| **Shares** | {filled_qty} |
| **Execution Price** | {filled_price_str} |
| **Total Value** | {total_val} |
| **Status** | `{order.status.upper()}` |
| **Executed At** | {order.filled_at or datetime.now().isoformat()} |

### Execution Mode
{simulated_note}

{"### ⚠️ Rejection Reason\n" + order.error_message if order.error_message else ""}

---
*Trade submitted at: {datetime.now().isoformat()}*
*Request ID: {pending.get("request_id", "?")}*
"""

        state["report_markdown"] = execution_report
        state["routing_decision"] = "completed"

        logger.info(f"[BROKER] Order {order_id} → {order.status.upper()}")
        logger.info("[APPROVAL EXECUTION NODE COMPLETE - SUCCESS]")
        
    except Exception as e:
        logger.error(f"Trade execution failed: {str(e)}")
        state["report_markdown"] = f"""# Trade Execution Failed

## ❌ Error

Your trade could not be executed:

**Reason:** {str(e)}

Please contact support or retry with valid parameters.
"""
        state["error_count"] += 1
        logger.info("[APPROVAL EXECUTION NODE COMPLETE - ERROR]")
    
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
    2. Consolidates findings into final report
    3. If report_markdown already exists (from research/general_q nodes), uses it
    4. Otherwise builds from raw data
    5. Returns completed state
    
    Args:
        state: Current graph state
        
    Returns:
        State with complete report_markdown
    """
    logger.info("=" * 80)
    logger.info("[ENTERING REPORTING NODE]")
    logger.info("-" * 80)
    
    # If report_markdown is already populated from research or general_q node, use it
    if state.get("report_markdown"):
        logger.info("Using pre-generated report from analysis node")
        logger.info("Report generation complete")
        logger.info("[REPORTING NODE COMPLETE]")
        logger.info("=" * 80)
        return state
    
    # Otherwise, build from raw data (for fallback paths)
    if state.get("research_data") and state["current_target_ticker"]:
        ticker = state["current_target_ticker"]
        data = state["research_data"]
        
        if "error" in data:
            report = f"### Error Processing {ticker}\n\n{data['error']}"
        else:
            # Build report from Alpha Vantage data
            report = f"""# Financial Research Report: {ticker}

## Current Market Data
- **Price:** ${data.get('price', 'N/A')}
- **Daily Change:** {data.get('change_percent', 'N/A')}%
- **Volume:** {data.get('volume', 'N/A'):,}
- **Data Source:** {data.get('data_source', 'N/A')}
- **Last Updated:** {data.get('timestamp', 'N/A')}

## Summary
This report was generated using real market data from Alpha Vantage API combined with Qwen AI analysis.
"""
        
        state["report_markdown"] = report
    
    logger.info("Report generation complete")
    logger.info("[REPORTING NODE COMPLETE]")
    logger.info("=" * 80)
    
    return state


# ============================================================================
# CONDITIONAL ROUTING LOGIC
# ============================================================================

def portfolio_node(state: GraphState) -> GraphState:
    """
    Portfolio Analysis Node — analyses the user's current simulation holdings.

    Steps:
    1. Fetch account info from the broker (MockSimulationEngine)
    2. Pull live prices for every holding in parallel (Alpha Vantage)
    3. Compute market value, allocation %, unrealised P&L, risk score
    4. Call Qwen for a concise risk assessment + recommendations
    5. Build a structured markdown report
    """
    import concurrent.futures as _cf

    logger.info("=" * 80)
    logger.info("[ENTERING PORTFOLIO NODE]")
    logger.info("-" * 80)

    try:
        from app.trading import get_broker_for_user, get_account_id_for_user

        broker = get_broker_for_user()
        account_id = get_account_id_for_user()

        account_info = asyncio.run(broker.get_account_info(account_id))
        positions: dict = account_info.get("positions", {})
        cash: float = float(account_info.get("cash", 0.0))

        logger.info(f"Account loaded: {len(positions)} position(s), ${cash:,.2f} cash")

        if not positions:
            state["report_markdown"] = (
                "# 📊 Portfolio Analysis\n\n"
                "## Empty Portfolio\n\n"
                "No open positions found. Start trading to build your portfolio!\n\n"
                f"**Available Cash:** ${cash:,.2f}"
            )
            state["routing_decision"] = "completed"
            logger.info("[PORTFOLIO NODE COMPLETE — empty portfolio]")
            logger.info("=" * 80)
            return state

        # ── Live price fetch (parallel) ───────────────────────────────────
        tickers = list(positions.keys())
        logger.info(f"Fetching live prices for: {', '.join(tickers)}")
        with _cf.ThreadPoolExecutor(max_workers=min(len(tickers), 5)) as pool:
            price_map = {
                t: pool.submit(financial_tools.get_stock_data, t)
                for t in tickers
            }
            live = {t: f.result() for t, f in price_map.items()}

        # ── Compute per-position metrics ──────────────────────────────────
        holdings = []
        invested_value = 0.0
        for ticker, pos in positions.items():
            shares = float(pos.get("quantity", 0))
            avg_cost = float(pos.get("average_cost", 0))
            live_price = float(live[ticker].get("price", avg_cost))
            market_val = shares * live_price
            cost_basis = shares * avg_cost
            unrealised_pnl = market_val - cost_basis
            unrealised_pct = (unrealised_pnl / cost_basis * 100) if cost_basis else 0.0
            invested_value += market_val
            holdings.append({
                "ticker": ticker,
                "shares": shares,
                "avg_cost": avg_cost,
                "live_price": live_price,
                "market_value": market_val,
                "cost_basis": cost_basis,
                "unrealised_pnl": unrealised_pnl,
                "unrealised_pct": unrealised_pct,
            })

        holdings.sort(key=lambda h: h["market_value"], reverse=True)
        total_value = invested_value + cash
        for h in holdings:
            h["allocation_pct"] = (h["market_value"] / total_value * 100) if total_value else 0.0
        cash_pct = (cash / total_value * 100) if total_value else 0.0
        total_pnl = sum(h["unrealised_pnl"] for h in holdings)
        total_pnl_pct = (total_pnl / (total_value - total_pnl) * 100) if (total_value - total_pnl) else 0.0

        # ── Risk score ────────────────────────────────────────────────────
        max_alloc = max(h["allocation_pct"] for h in holdings)
        n = len(holdings)

        # Herfindahl-Hirschman Index: sum of squared allocation weights (0→1).
        # HHI = 1.0 means a single-stock portfolio (maximum concentration).
        # HHI ≤ 0.18 is conventionally "diversified" across 5+ equal positions.
        hhi = sum((h["allocation_pct"] / 100) ** 2 for h in holdings)
        # Normalised HHI removes the cash drag so it reflects equity concentration.

        if max_alloc > 50 or n < 2 or hhi > 0.5:
            risk_level = "HIGH 🔴"
        elif max_alloc > 30 or n < 4 or hhi > 0.25:
            risk_level = "MEDIUM 🟡"
        else:
            risk_level = "LOW 🟢"

        logger.info(
            f"Portfolio: total=${total_value:,.2f}, "
            f"invested=${invested_value:,.2f}, cash=${cash:,.2f}, "
            f"P&L={total_pnl:+,.2f} ({total_pnl_pct:+.1f}%), risk={risk_level}"
        )

        # ── Qwen analysis ─────────────────────────────────────────────────
        logger.info("Requesting Qwen portfolio risk analysis...")
        holding_lines = "\n".join(
            f"  - {h['ticker']}: {h['shares']:.4f} shares @ ${h['live_price']:.2f} "
            f"= ${h['market_value']:.2f} ({h['allocation_pct']:.1f}%), "
            f"P&L {h['unrealised_pnl']:+.2f} ({h['unrealised_pct']:+.1f}%)"
            for h in holdings
        )
        llm_prompt = (
            f"Analyse this paper trading portfolio and provide:\n"
            f"1. Concentration / diversification risk assessment\n"
            f"2. Sector exposure commentary\n"
            f"3. Two to three specific, actionable recommendations\n"
            f"4. Overall portfolio health score (1-10) with one-line rationale\n\n"
            f"Portfolio summary:\n"
            f"  Total value: ${total_value:,.2f}\n"
            f"  Cash: ${cash:,.2f} ({cash_pct:.1f}%)\n"
            f"  Invested: ${invested_value:,.2f}\n"
            f"  Unrealised P&L: {total_pnl:+,.2f} ({total_pnl_pct:+.1f}%)\n"
            f"  Herfindahl-Hirschman Index (concentration): {hhi:.3f} "
            f"({'highly concentrated' if hhi > 0.5 else 'moderately concentrated' if hhi > 0.25 else 'diversified'})\n"
            f"  Risk level: {risk_level}\n"
            f"Positions:\n{holding_lines}\n\n"
            f"Be concise and direct. Use markdown bullet points."
        )
        analysis = call_qwen_for_general_qa(llm_prompt)

        # ── Build report ──────────────────────────────────────────────────
        pnl_sign = "+" if total_pnl >= 0 else ""
        lines = [
            "# 📊 Portfolio Analysis",
            "",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Total Value | ${total_value:,.2f} |",
            f"| Invested | ${invested_value:,.2f} |",
            f"| Cash | ${cash:,.2f} ({cash_pct:.1f}%) |",
            f"| Unrealised P&L | {pnl_sign}${total_pnl:,.2f} ({pnl_sign}{total_pnl_pct:.1f}%) |",
            f"| Concentration (HHI) | {hhi:.3f} — {'high' if hhi > 0.5 else 'moderate' if hhi > 0.25 else 'diversified'} |",
            f"| Risk Level | {risk_level} |",
            f"| Positions | {n} |",
            "",
            "## Holdings",
            "",
            "| Ticker | Shares | Avg Cost | Live Price | Market Value | Allocation | P&L |",
            "|---|---|---|---|---|---|---|",
        ]
        for h in holdings:
            pnl_str = f"{h['unrealised_pnl']:+.2f} ({h['unrealised_pct']:+.1f}%)"
            lines.append(
                f"| **{h['ticker']}** | {h['shares']:.4f} | "
                f"\\${h['avg_cost']:.2f} | \\${h['live_price']:.2f} | "
                f"\\${h['market_value']:.2f} | {h['allocation_pct']:.1f}% | {pnl_str} |"
            )
        lines += [
            f"| 💵 Cash | — | — | — | \\${cash:,.2f} | {cash_pct:.1f}% | — |",
            "",
            "## 🤖 AI Risk Analysis",
            "",
            analysis,
        ]
        state["report_markdown"] = "\n".join(lines)
        state["routing_decision"] = "completed"

        logger.info("[PORTFOLIO NODE COMPLETE]")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Portfolio analysis failed: {e}")
        state["error_count"] = state.get("error_count", 0) + 1
        state["report_markdown"] = f"# Portfolio Analysis\n\n**Error:** {e}"
        state["routing_decision"] = "completed"

    return state


def route_after_triage(state: GraphState) -> str:
    """
    Conditional router that determines the next node based on routing_decision.
    
    This function is called after the Triage Node and reads state["routing_decision"]
    to determine which downstream node to invoke:
    - "research" -> research_node (detailed analysis)
    - "direct_trade" -> trading_node (immediate trade with approval)
    - "general_q" -> general_q_node (Q&A)
    
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
    elif decision == "direct_trade":
        logger.info("[CONDITIONAL EDGE] Taking DIRECT_TRADE path")
        return "trading"
    elif decision == "portfolio":
        logger.info("[CONDITIONAL EDGE] Taking PORTFOLIO path")
        return "portfolio"
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
        +-> research_node --------+
        |                          |
        +-> trading_node ----------+-> approval_execution_node (conditional)
        |                          |
        +-> general_q_node --------+
        |                          |
        +-- reporting_node (END)
    ```
    
    The approval_execution_node only runs if approval_status == "approved"
    
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
    graph.add_node("trading", trading_node)
    graph.add_node("general_q", general_q_node)
    graph.add_node("portfolio", portfolio_node)
    graph.add_node("approval_execution", approval_execution_node)
    graph.add_node("reporting", reporting_node)
    
    logger.info("✓ Nodes added: triage, research, trading, general_q, portfolio, approval_execution, reporting")
    
    # Define entry point
    graph.set_entry_point("triage")
    logger.info("✓ Entry point: triage")
    
    # Add conditional edge from triage
    graph.add_conditional_edges(
        source="triage",
        path=route_after_triage,
        path_map={
            "research": "research",
            "trading": "trading",
            "general_q": "general_q",
            "portfolio": "portfolio",
        },
    )
    logger.info("✓ Conditional edge added: triage -> (research | trading | general_q | portfolio)")
    
    graph.add_edge("research", "approval_execution")
    graph.add_edge("trading", "approval_execution")
    graph.add_edge("general_q", "approval_execution")
    graph.add_edge("portfolio", "approval_execution")
    logger.info("✓ Edges added: research -> approval_execution, trading -> approval_execution, general_q -> approval_execution, portfolio -> approval_execution")
    
    # Connect approval_execution to reporting
    graph.add_edge("approval_execution", "reporting")
    logger.info("✓ Edge added: approval_execution -> reporting")
    
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
    logger.info("║" + "  CORPORATE INTELLIGENCE ENGINE — QWEN EDITION  ".center(78) + "║")
    logger.info("║" + "  Tri-Agent Committee · LangGraph · Robinhood MCP  ".center(78) + "║")
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
