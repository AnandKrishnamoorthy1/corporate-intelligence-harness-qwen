"""
Corporate Intelligence Engine - Streamlit Frontend

An interactive web UI for the corporate-intelligence-engine that connects to the
FastAPI backend and provides real-time visualization of agent reasoning steps.

Features:
  - Chat interface for user queries
  - Real-time agent activity visualization
  - Structured report display
  - Execution time tracking
  - Error handling and recovery

Run with:
  streamlit run frontend.py
"""

import streamlit as st
import requests
import json
from datetime import datetime
from typing import Optional

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Corporate Intelligence Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-title {
        text-align: center;
        color: #1f77b4;
        margin-bottom: 30px;
    }
    
    .status-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 5px;
        border-left: 4px solid #1f77b4;
    }
    
    .log-entry {
        font-family: monospace;
        font-size: 0.85em;
        line-height: 1.5;
        color: #333;
    }
    
    .success-badge {
        color: #28a745;
        font-weight: bold;
    }
    
    .error-badge {
        color: #dc3545;
        font-weight: bold;
    }
    
    .routing-badge {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 3px;
        font-weight: bold;
        margin: 5px 0;
    }
    
    .research-badge {
        background-color: #e3f2fd;
        color: #1565c0;
    }
    
    .general-badge {
        background-color: #f3e5f5;
        color: #6a1b9a;
    }
    
    .metric-box {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        text-align: center;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SESSION STATE MANAGEMENT
# ============================================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_response" not in st.session_state:
    st.session_state.last_response = None

if "api_available" not in st.session_state:
    st.session_state.api_available = None


# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

API_BASE_URL = "http://localhost:8000"
API_HEALTH_ENDPOINT = f"{API_BASE_URL}/health"
API_ANALYZE_ENDPOINT = f"{API_BASE_URL}/api/analyze"
REQUEST_TIMEOUT = 60  # seconds


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def check_api_health() -> bool:
    """
    Check if the FastAPI backend is running and healthy.
    
    Returns:
        bool: True if API is available, False otherwise
    """
    try:
        response = requests.get(API_HEALTH_ENDPOINT, timeout=5)
        return response.status_code == 200
    except Exception as e:
        st.session_state.api_available = False
        return False


def call_analysis_api(user_input: str) -> Optional[dict]:
    """
    Call the FastAPI backend to analyze the user input.
    
    Args:
        user_input: User query
        
    Returns:
        Response JSON if successful, None otherwise
    """
    try:
        payload = {"user_input": user_input}
        
        response = requests.post(
            API_ANALYZE_ENDPOINT,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            return None
            
    except requests.exceptions.ConnectionError:
        st.error(
            "❌ **Backend Connection Error**: Could not reach the FastAPI server. "
            "Please ensure the backend is running with `uvicorn backend:app --reload`"
        )
        return None
    except requests.exceptions.Timeout:
        st.error("❌ **Timeout Error**: The backend took too long to respond.")
        return None
    except Exception as e:
        st.error(f"❌ **Error**: {str(e)}")
        return None


def get_routing_badge_class(routing_decision: str) -> str:
    """Get CSS class for routing decision badge."""
    if routing_decision == "research":
        return "research-badge"
    elif routing_decision == "general_q":
        return "general-badge"
    else:
        return ""


def get_routing_badge_label(routing_decision: str) -> str:
    """Get display label for routing decision."""
    if routing_decision == "research":
        return "🔬 Research"
    elif routing_decision == "general_q":
        return "💡 General Question"
    else:
        return "❓ Unknown"


# ============================================================================
# PAGE HEADER
# ============================================================================

st.markdown(
    "<h1 class='main-title'>📊 Corporate Intelligence & Earnings Analyst Engine</h1>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <p style='text-align: center; color: #666; margin-bottom: 20px;'>
    Powered by Multi-Agent AI Orchestration | Real-time Financial Intelligence
    </p>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
# SIDEBAR - STATUS & HELP
# ============================================================================

with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    # API Health Status
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("**Backend Status**")
    with col2:
        if check_api_health():
            st.markdown("<span style='color: #28a745; font-weight: bold;'>✓ Online</span>", unsafe_allow_html=True)
            st.session_state.api_available = True
        else:
            st.markdown("<span style='color: #dc3545; font-weight: bold;'>✗ Offline</span>", unsafe_allow_html=True)
            st.session_state.api_available = False
    
    if not st.session_state.api_available:
        st.warning(
            "⚠️ **Backend not running!**\n\n"
            "Start the FastAPI server in another terminal:\n\n"
            "```bash\n"
            "uvicorn backend:app --reload\n"
            "```"
        )
    
    st.divider()
    
    st.markdown("### 📖 Help")
    st.markdown("""
    **What can I ask?**
    
    **Research Queries:**
    - "Analyze NVDA earnings"
    - "What's the current price of TSLA?"
    - "Show me Tesla stock forecast"
    
    **General Questions:**
    - "Top ML frameworks 2024?"
    - "What is quantitative analysis?"
    - "Explain financial derivatives"
    
    **How it works:**
    1. Enter your query
    2. Agent triages request (research vs general)
    3. Routes to appropriate analyzer
    4. Generates structured report
    """)
    
    st.divider()
    
    st.markdown("### 🔗 Links")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("[📚 Docs](http://localhost:8000/docs)")
    with col2:
        st.markdown("[🔄 Reload](javascript:location.reload())")
    with col3:
        st.markdown("[ℹ️ About](#)")


# ============================================================================
# MAIN CONTENT - CHAT INTERFACE
# ============================================================================

st.markdown("### 💬 Analysis Interface")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Display metadata if it's an assistant response
        if message["role"] == "assistant" and "metadata" in message:
            metadata = message["metadata"]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Routing Decision",
                    get_routing_badge_label(metadata.get("routing_decision", "Unknown")),
                )
            
            with col2:
                st.metric(
                    "Execution Time",
                    f"{metadata.get('execution_time_ms', 0):.1f}ms"
                )
            
            with col3:
                st.metric(
                    "Log Entries",
                    len(metadata.get("logs", []))
                )


# ============================================================================
# USER INPUT & PROCESSING
# ============================================================================

st.markdown("---")

# Chat input box
user_input = st.chat_input(
    "Enter a ticker or analysis prompt (e.g., Analyze NVDA)...",
    key="user_input",
)

if user_input:
    # Check API availability first
    if not check_api_health():
        st.error(
            "❌ **Cannot process request**: Backend is not running. "
            "Please start the FastAPI server first."
        )
    else:
        # Add user message to chat history
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
        })
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Create status container for real-time updates
        with st.status("🚀 Orchestrating AI Agents...", expanded=True) as status:
            st.write("Initiating multi-agent analysis workflow...")
            
            # Call the API
            response = call_analysis_api(user_input)
            
            if response:
                # Display logs as they are received
                st.write("---")
                st.write("### 📋 Agent Execution Trace")
                
                for log_entry in response.get("logs", []):
                    st.write(f"<div class='log-entry'>{log_entry}</div>", unsafe_allow_html=True)
                
                # Check for errors
                if response.get("status") == "error":
                    status.update(
                        label="❌ Analysis Failed!",
                        state="error",
                        expanded=False,
                    )
                    st.error(f"Error: {response.get('error_message', 'Unknown error')}")
                else:
                    # Update status to complete
                    status.update(
                        label=f"✅ Analysis Complete! ({response.get('execution_time_ms', 0):.1f}ms)",
                        state="complete",
                        expanded=False,
                    )
                    
                    # Add assistant response to chat history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response.get("report_markdown", ""),
                        "metadata": {
                            "routing_decision": response.get("routing_decision", ""),
                            "logs": response.get("logs", []),
                            "execution_time_ms": response.get("execution_time_ms", 0),
                        }
                    })
                    
                    # Display final report
                    st.markdown("---")
                    st.markdown("### 📊 Final Report")
                    
                    st.markdown(
                        f"<div class='routing-badge {get_routing_badge_class(response.get('routing_decision'))}'>"
                        f"{get_routing_badge_label(response.get('routing_decision'))}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    
                    st.markdown(response.get("report_markdown", ""))
            else:
                status.update(
                    label="❌ Request Failed",
                    state="error",
                    expanded=False,
                )


# ============================================================================
# FOOTER & INFO
# ============================================================================

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.info("💻 **Frontend**: Streamlit")

with col2:
    st.info("⚙️ **Backend**: FastAPI + Uvicorn")

with col3:
    st.info("🧠 **Orchestration**: LangGraph State Machine")

st.markdown("""
---
<p style='text-align: center; color: #999; font-size: 0.9em;'>
Corporate Intelligence Engine | AI State Graph | Financial Research
</p>
""", unsafe_allow_html=True)
