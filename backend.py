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
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from loguru import logger
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field, ConfigDict
from uvicorn import run
from config.settings import settings

# Import the orchestrator graph and models
try:
    from orchestrator import build_graph, GraphState, ApprovalResponse
except ImportError:
    raise ImportError(
        "Could not import orchestrator. Ensure orchestrator.py is in the same directory."
    )

# Import LLM initialization
try:
    from app.llm import initialize_qwen
except ImportError:
    raise ImportError(
        "Could not import initialize_qwen. Ensure app/llm modules are configured."
    )

# ============================================================================
# REQUEST TRACKING FOR STREAMING LOGS
# ============================================================================

class RequestTracker:
    """Tracks active requests and their logs for streaming."""
    
    def __init__(self):
        self.requests: Dict[str, Dict[str, Any]] = {}
    
    def create_request(self, user_input: str) -> str:
        """Create a new request and return its ID."""
        request_id = str(uuid.uuid4())[:8]  # Shorter ID for readability
        self.requests[request_id] = {
            "user_input": user_input,
            "logs": [],
            "status": "processing",
            "created_at": datetime.now().isoformat(),
            "last_log_time": datetime.now(),
            "completed_at": None,
        }
        return request_id
    
    def add_log(self, request_id: str, log_entry: str):
        """Add a log entry to a request."""
        if request_id in self.requests:
            self.requests[request_id]["logs"].append(log_entry)
            self.requests[request_id]["last_log_time"] = datetime.now()
    
    def get_logs(self, request_id: str) -> List[str]:
        """Get all logs for a request."""
        if request_id in self.requests:
            return self.requests[request_id]["logs"].copy()
        return []
    
    def get_status(self, request_id: str) -> Dict[str, Any]:
        """Get status and logs for a request."""
        if request_id in self.requests:
            req = self.requests[request_id]
            return {
                "request_id": request_id,
                "status": req["status"],
                "logs": req["logs"],
                "log_count": len(req["logs"]),
                "created_at": req["created_at"],
                "last_log_time": req["last_log_time"].isoformat(),
                "completed_at": req["completed_at"],
            }
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
    
    def complete_request(self, request_id: str):
        """Mark a request as completed."""
        if request_id in self.requests:
            self.requests[request_id]["status"] = "completed"
            self.requests[request_id]["completed_at"] = datetime.now().isoformat()
    
    def cleanup_old_requests(self, max_age_minutes: int = 60):
        """Clean up completed requests older than max_age_minutes."""
        now = datetime.now()
        to_delete = []
        for request_id, req in self.requests.items():
            if req["status"] == "completed" and req["completed_at"]:
                completed_time = datetime.fromisoformat(req["completed_at"])
                if (now - completed_time).total_seconds() > (max_age_minutes * 60):
                    to_delete.append(request_id)
        for request_id in to_delete:
            del self.requests[request_id]


# Global request tracker
request_tracker = RequestTracker()

# ============================================================================
# PYDANTIC MODELS FOR API
# ============================================================================

class AnalysisRequest(BaseModel):
    """Request model for the analysis endpoint."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_input": "Analyze the latest earnings for NVDA"
            }
        }
    )
    
    user_input: str = Field(
        ...,
        description="User query or prompt for the analysis engine",
        min_length=1,
        max_length=2000
    )


class AnalysisResponse(BaseModel):
    """Response model for the analysis endpoint."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "abc123de",
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
    )
    
    request_id: str = Field(
        description="Unique request ID for tracking and polling logs"
    )
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


# ============================================================================
# STARTUP & SHUTDOWN EVENTS (LIFESPAN)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print("\n" + "=" * 80)
    print("CORPORATE INTELLIGENCE ENGINE - FASTAPI BACKEND")
    print("=" * 80)
    print(f"Server started at: {datetime.now().isoformat()}")
    
    # Initialize Qwen LLM with API key
    try:
        print("Initializing Qwen LLM...")
        initialize_qwen()
        print("✓ Qwen LLM initialized successfully")
    except ValueError as e:
        print(f"✗ Failed to initialize Qwen: {str(e)}")
        print("  Ensure QWEN_API_KEY environment variable is set")
        raise
    
    print("Available endpoints:")
    print("  - POST /api/analyze")
    print("  - GET /api/requests/{request_id}/status")
    print("  - GET /health")
    print("  - GET /api/routes")
    print("  - GET /docs (API documentation)")
    print("=" * 80 + "\n")
    
    yield
    
    # Shutdown
    print("\n" + "=" * 80)
    print("CORPORATE INTELLIGENCE ENGINE - SERVER SHUTDOWN")
    print("=" * 80 + "\n")


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Corporate Intelligence Engine API",
    description="AI State Graph API for financial research and corporate intelligence",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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
    """Loguru-based log capture for API responses with request tracking."""
    
    def __init__(self):
        self.logs: List[str] = []
        self.sink_id = None
        self.request_id: Optional[str] = None
    
    def sink(self, message):
        """Loguru sink function to capture messages."""
        # Extract the formatted message
        log_text = message.record["message"]
        level = message.record["level"].name
        log_entry = f"[{level}] {log_text}"
        
        # Add to local list
        self.logs.append(log_entry)
        
        # Also add to request tracker if we have a request_id
        if self.request_id:
            request_tracker.add_log(self.request_id, log_entry)
    
    def clear(self):
        """Clear the log buffer."""
        self.logs = []
    
    def get_logs(self) -> List[str]:
        """Get all captured logs."""
        return self.logs.copy()
    
    @contextmanager
    def capture(self, request_id: Optional[str] = None):
        """Context manager to enable/disable log capture."""
        # Set request ID for tracking
        self.request_id = request_id
        
        # Add sink for capturing
        self.clear()
        sink_id = logger.add(self.sink, format="{message}", level="INFO")
        try:
            yield
        finally:
            # Remove sink after capture
            logger.remove(sink_id)
            self.request_id = None


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
    2. Creates a request ID for tracking logs
    3. Routes it through the state machine (triage → research/general_q → reporting)
    4. Captures all agent reasoning logs (available via /api/requests/{request_id}/status)
    5. Returns structured response with logs and final report
    
    Args:
        request: AnalysisRequest with user_input
        
    Returns:
        AnalysisResponse with request_id, status, routing_decision, logs, and report_markdown
        
    Raises:
        HTTPException: If execution fails
    """
    start_time = datetime.now()
    
    # Create request for tracking
    request_id = request_tracker.create_request(request.user_input)
    logger.info(f"Created request: {request_id}")
    
    try:
        # Log the incoming request
        logger.info(f"Received analysis request")
        logger.info(f"User Input: {request.user_input}")
        
        # Capture logs during graph execution with request tracking
        with log_capture.capture(request_id=request_id):
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
        
        # Mark request as completed
        request_tracker.complete_request(request_id)
        
        # Construct response
        response = AnalysisResponse(
            request_id=request_id,
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
        
        request_tracker.complete_request(request_id)
        
        return AnalysisResponse(
            request_id=request_id,
            status="error",
            routing_decision="error",
            logs=log_capture.get_logs(),
            report_markdown="",
            error_message=error_msg,
            execution_time_ms=execution_time,
        )


@app.get("/api/requests/{request_id}/status", tags=["Request Tracking"])
async def get_request_status(request_id: str) -> Dict[str, Any]:
    """
    Get status and logs for a specific request.
    
    This endpoint allows polling for progress on an analysis request.
    Frontend can call this to get live logs while waiting for the full response.
    
    Args:
        request_id: The request ID to check status for
        
    Returns:
        dict: Status information including logs, timing, and completion state
        
    Raises:
        HTTPException: If request_id not found
    """
    return request_tracker.get_status(request_id)


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
        port=settings.backend_port,
        log_level="info",
    )
