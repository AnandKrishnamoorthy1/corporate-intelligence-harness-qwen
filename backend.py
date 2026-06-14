"""
Corporate Intelligence Engine - FastAPI Backend

A RESTful backend service that orchestrates the AI state graph and exposes it
through a clean HTTP API for the Streamlit frontend to consume.

Endpoints:
  - POST /api/analyze: Execute the orchestrator graph with user input
  - GET /health: Health check endpoint

The backend captures all agent reasoning steps and returns them as structured logs
so the frontend can display real-time agent activity to the user.
"""

import logging
import json
import io
import sys
from datetime import datetime
from typing import List
from contextlib import redirect_stdout, redirect_stderr

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from uvicorn import run

# Import the orchestrator graph and models
try:
    from orchestrator import build_graph, GraphState
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
        description="Execution status: 'success', 'error', or 'partial'"
    )
    routing_decision: str = Field(
        description="The routing path taken: 'research' or 'general_q'"
    )
    logs: List[str] = Field(
        description="Sequential log entries from the agent execution",
        default_factory=list
    )
    report_markdown: str = Field(
        description="Final formatted report in Markdown"
    )
    error_message: str = Field(
        default="",
        description="Error message if status is 'error'"
    )
    execution_time_ms: float = Field(
        description="Total execution time in milliseconds"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "routing_decision": "research",
                "logs": [
                    "[ENTERING TRIAGE NODE]",
                    "LLM Response: {routing_path: research, ticker: NVDA}",
                    "[CONDITIONAL EDGE] Taking RESEARCH path",
                    "[ENTERING RESEARCH NODE]",
                    "Research complete. 14 data points collected."
                ],
                "report_markdown": "# Financial Research Report: NVDA\n\n...",
                "error_message": "",
                "execution_time_ms": 245.3
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
# LOGGING SETUP - CAPTURE FOR API RESPONSES
# ============================================================================

class LogCapture(logging.Handler):
    """Custom logging handler to capture log messages for API responses."""
    
    def __init__(self):
        super().__init__()
        self.logs: List[str] = []
        self.setLevel(logging.INFO)
    
    def emit(self, record):
        """Capture log records as formatted strings."""
        try:
            msg = self.format(record)
            self.logs.append(msg)
        except Exception:
            self.handleError(record)
    
    def clear(self):
        """Clear the log buffer."""
        self.logs = []
    
    def get_logs(self) -> List[str]:
        """Get all captured logs."""
        return self.logs.copy()


# Global log capture handler
log_capture = LogCapture()
log_capture.setFormatter(
    logging.Formatter(
        fmt="[%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
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
        print(f"\n{'=' * 80}")
        print(f"[API] Received analysis request")
        print(f"[API] User Input: {request.user_input}")
        print(f"{'=' * 80}\n")
        
        # Clear previous logs
        log_capture.clear()
        
        # Add log capture handler to orchestrator logger
        orchestrator_logger = logging.getLogger("corporate-intelligence-engine")
        if log_capture not in orchestrator_logger.handlers:
            orchestrator_logger.addHandler(log_capture)
        
        # Build and compile the graph
        print("[API] Building state graph...")
        graph = build_graph()
        print("[API] Graph compiled successfully\n")
        
        # Initialize state
        initial_state: GraphState = {
            "user_input": request.user_input,
            "current_target_ticker": "",
            "routing_decision": "",
            "research_data": {},
            "report_markdown": "",
            "error_count": 0,
        }
        
        # Execute the graph
        print(f"[API] Executing orchestrator graph...")
        final_state = graph.invoke(initial_state)
        print(f"[API] Graph execution complete\n")
        
        # Get captured logs
        captured_logs = log_capture.get_logs()
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds() * 1000  # ms
        
        # Construct response
        response = AnalysisResponse(
            status="success",
            routing_decision=final_state.get("routing_decision", "unknown"),
            logs=captured_logs,
            report_markdown=final_state.get("report_markdown", ""),
            error_message="",
            execution_time_ms=execution_time,
        )
        
        print(f"[API] Response prepared: {len(captured_logs)} log entries captured")
        print(f"[API] Execution time: {execution_time:.1f}ms\n")
        
        return response
        
    except Exception as e:
        # Calculate execution time even on error
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        error_msg = f"Orchestrator execution failed: {str(e)}"
        print(f"\n[API ERROR] {error_msg}")
        
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
