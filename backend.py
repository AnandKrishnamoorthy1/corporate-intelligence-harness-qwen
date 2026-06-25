"""
Corporate Intelligence Engine - FastAPI Backend

A RESTful backend service that orchestrates the AI state graph and exposes it
through a clean HTTP API for the Streamlit frontend to consume.

Endpoints:
  - POST /api/analyze: Execute the orchestrator graph with user input
  - POST /api/approve/{request_id}: Human approval of recommendations
  - GET /health: Health check endpoint

The backend captures all agent reasoning steps and returns them as structured logs
so the frontend can display real-time agent activity to the user.

Supports human-in-loop checkpoints for critical recommendations (BUY/SELL).
"""

import json
import sys
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from loguru import logger
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from uvicorn import run

# Import the orchestrator graph and models
try:
    from orchestrator import build_graph, GraphState, ApprovalResponse
except ImportError:
    raise ImportError(
        "Could not import orchestrator. Ensure orchestrator.py is in the same directory."
    )

# ============================================================================
# PYDANTIC MODELS FOR API
# ============================================================================

class AnalysisRequest(BaseModel):
    """Request model for the analysis endpoint."""
    
    user_input: str = Field(
        ...,
        description="User query or prompt for the analysis engine",
        min_length=1,
        max_length=2000,
        example="Analyze the latest earnings for NVDA"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_input": "Analyze the latest earnings for NVDA"
            }
        }


class AnalysisResponse(BaseModel):
    """Response model for the analysis endpoint."""
    
    status: str = Field(
        description="Execution status: 'success', 'error', 'awaiting_approval', or 'partial'"
    )
    routing_decision: str = Field(
        description="The routing path taken: 'research', 'general_q', 'awaiting_approval', 'completed'"
    )
    logs: List[str] = Field(
        description="Sequential log entries from the agent execution",
        default_factory=list
    )
    report_markdown: str = Field(
        description="Final formatted report in Markdown or interim analysis"
    )
    error_message: str = Field(
        default="",
        description="Error message if status is 'error'"
    )
    execution_time_ms: float = Field(
        description="Total execution time in milliseconds"
    )
    pending_approval: Optional[Dict[str, Any]] = Field(
        default=None,
        description="If status='awaiting_approval', contains the approval request details"
    )
    approval_status: Optional[str] = Field(
        default=None,
        description="Approval status: 'pending', 'approved', 'rejected'"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "awaiting_approval",
                "routing_decision": "awaiting_approval",
                "logs": [
                    "[ENTERING TRIAGE NODE]",
                    "[EXTERNAL TOOL] Calling Alpha Vantage API...",
                    "[EXTERNAL TOOL RESULT] Alpha Vantage (REAL API)",
                    "[CHECKPOINT] Recommendation requires human approval!"
                ],
                "report_markdown": "# Financial Research Report: NVDA\n\n...",
                "error_message": "",
                "execution_time_ms": 2450.3,
                "pending_approval": {
                    "request_id": "NVDA-1234567890",
                    "action": "BUY",
                    "ticker": "NVDA",
                    "reasoning": "Qwen analysis recommends BUY for NVDA",
                    "confidence": 0.92,
                    "timestamp": "2026-06-24T14:30:00"
                },
                "approval_status": "pending"
            }
        }


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Corporate Intelligence Engine API",
    description="AI State Graph API for financial research and corporate intelligence",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your Streamlit domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# LOGGING SETUP - CAPTURE FOR API RESPONSES WITH LOGURU
# ============================================================================

class LogCapture:
    """Loguru-based log capture for API responses."""
    
    def __init__(self):
        self.logs: List[str] = []
        self.sink_id = None
    
    def sink(self, message):
        """Loguru sink function to capture messages."""
        # Extract the formatted message
        log_text = message.record["message"]
        level = message.record["level"].name
        self.logs.append(f"[{level}] {log_text}")
    
    def clear(self):
        """Clear the log buffer."""
        self.logs = []
    
    def get_logs(self) -> List[str]:
        """Get all captured logs."""
        return self.logs.copy()
    
    @contextmanager
    def capture(self):
        """Context manager to enable/disable log capture."""
        # Add sink for capturing
        self.clear()
        sink_id = logger.add(self.sink, format="{message}", level="INFO")
        try:
            yield
        finally:
            # Remove sink after capture
            logger.remove(sink_id)


# Global log capture instance
log_capture = LogCapture()

# Configure loguru for stderr (console output)
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<level>{time:YYYY-MM-DD HH:mm:ss}</level> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for monitoring and load balancing.
    
    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": "corporate-intelligence-engine",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/analyze", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    """
    Execute the AI orchestrator graph with the given user input.
    
    This endpoint:
    1. Receives a user query
    2. Routes it through the state machine (triage → research/general_q → reporting)
    3. Captures all agent reasoning logs
    4. Returns structured response with logs and final report
    
    Args:
        request: AnalysisRequest with user_input
        
    Returns:
        AnalysisResponse with status, routing_decision, logs, and report_markdown
        
    Raises:
        HTTPException: If execution fails
    """
    start_time = datetime.now()
    
    try:
        # Log the incoming request
        logger.info(f"Received analysis request")
        logger.info(f"User Input: {request.user_input}")
        
        # Capture logs during graph execution
        with log_capture.capture():
            # Build and compile the graph
            logger.info("Building state graph...")
            graph = build_graph()
            logger.info("Graph compiled successfully")
            
            # Initialize state
            initial_state: GraphState = {
                "user_input": request.user_input,
                "current_target_ticker": "",
                "routing_decision": "",
                "research_data": {},
                "report_markdown": "",
                "error_count": 0,
                "pending_approval": None,
                "approval_status": None,
            }
            
            # Execute the graph
            logger.info("Executing orchestrator graph...")
            final_state = graph.invoke(initial_state)
            logger.info("Graph execution complete")
        
        # Get captured logs
        captured_logs = log_capture.get_logs()
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds() * 1000  # ms
        
        # Determine response status based on approval state
        response_status = "success"
        if final_state.get("approval_status") == "pending":
            response_status = "awaiting_approval"
        elif final_state.get("error_count", 0) > 0:
            response_status = "partial"
        
        # Construct response
        response = AnalysisResponse(
            status=response_status,
            routing_decision=final_state.get("routing_decision", "unknown"),
            logs=captured_logs,
            report_markdown=final_state.get("report_markdown", ""),
            error_message="",
            execution_time_ms=execution_time,
            pending_approval=final_state.get("pending_approval"),
            approval_status=final_state.get("approval_status"),
        )
        
        logger.info(f"Response prepared: {len(captured_logs)} log entries captured")
        logger.info(f"Execution time: {execution_time:.1f}ms")
        
        return response
        
    except Exception as e:
        # Calculate execution time even on error
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        error_msg = f"Orchestrator execution failed: {str(e)}"
        logger.error(error_msg)
        
        return AnalysisResponse(
            status="error",
            routing_decision="error",
            logs=log_capture.get_logs(),
            report_markdown="",
            error_message=error_msg,
            execution_time_ms=execution_time,
        )


@app.get("/api/routes", tags=["Documentation"])
async def get_routes():
    """
    Return available routing paths for the AI orchestrator.
    
    Returns:
        dict: Available routing options
    """
    return {
        "routes": [
            {
                "path": "research",
                "description": "Stock research and financial analysis",
                "triggers": ["ticker", "earnings", "stock price", "analyst rating"]
            },
            {
                "path": "general_q",
                "description": "General knowledge questions",
                "triggers": ["frameworks", "tutorial", "how to", "what is"]
            }
        ]
    }


@app.post("/api/approve/{request_id}", tags=["Approval"])
async def approve_recommendation(request_id: str, response: ApprovalResponse) -> Dict[str, Any]:
    """
    Human approval endpoint for critical recommendations (BUY/SELL).
    
    This endpoint demonstrates human-in-loop decision gates. When the AI recommends
    a strong action (BUY/SELL), it pauses and waits for human approval through this
    endpoint before proceeding with the recommendation.
    
    Args:
        request_id: ID of the approval request to approve/reject
        response: ApprovalResponse with approved (bool) and approver_notes
        
    Returns:
        dict: Confirmation of approval status and next steps
        
    Note:
        In a production system, this would:
        1. Store the approval decision in a database
        2. Resume the paused orchestrator with the decision
        3. Trigger additional workflows (notification, execution, etc.)
        4. Audit the approval for compliance/regulatory purposes
    """
    print(f"\n{'=' * 80}")
    print(f"[APPROVAL] Received approval decision for request: {request_id}")
    print(f"[APPROVAL] Decision: {'APPROVED' if response.approved else 'REJECTED'}")
    print(f"[APPROVAL] Notes: {response.approver_notes}")
    print(f"{'=' * 80}\n")
    
    # In production, this would:
    # 1. Validate the request_id exists and is pending
    # 2. Store the approval decision
    # 3. Resume the orchestrator from the pending state
    # 4. Continue execution with the approved/rejected action
    
    action_verb = "approved" if response.approved else "rejected"
    
    return {
        "status": "success",
        "request_id": request_id,
        "approval_decision": action_verb,
        "message": f"Approval request {request_id} has been {action_verb}",
        "approver_notes": response.approver_notes,
        "next_steps": (
            "Action will be executed immediately"
            if response.approved
            else "Workflow has been cancelled"
        ),
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle validation errors."""
    return {
        "status": "error",
        "detail": f"Validation error: {str(exc)}"
    }


# ============================================================================
# STARTUP & SHUTDOWN EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on server startup."""
    print("\n" + "=" * 80)
    print("CORPORATE INTELLIGENCE ENGINE - FASTAPI BACKEND")
    print("=" * 80)
    print(f"Server started at: {datetime.now().isoformat()}")
    print("Available endpoints:")
    print("  - POST /api/analyze")
    print("  - GET /health")
    print("  - GET /api/routes")
    print("  - GET /docs (API documentation)")
    print("=" * 80 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown."""
    print("\n" + "=" * 80)
    print("CORPORATE INTELLIGENCE ENGINE - SERVER SHUTDOWN")
    print("=" * 80 + "\n")


# ============================================================================
# DEVELOPMENT SERVER
# ============================================================================

if __name__ == "__main__":
    print("\n" + "#" * 80)
    print("# Corporate Intelligence Engine - FastAPI Backend")
    print("# Starting Uvicorn server...")
    print("#" * 80 + "\n")
    
    run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
