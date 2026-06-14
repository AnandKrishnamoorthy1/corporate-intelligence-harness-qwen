# Web Layer Deployment Guide

Complete instructions for running the decoupled FastAPI backend and Streamlit frontend for the Corporate Intelligence Engine.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    CORPORATE INTELLIGENCE ENGINE                  │
│                     Web Layer Architecture                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────────────────┐    ┌─────────────────────────┐  │
│  │                             │    │                         │  │
│  │   STREAMLIT FRONTEND        │    │   FASTAPI BACKEND       │  │
│  │   (frontend.py)             │◄──►│   (backend.py)          │  │
│  │                             │    │                         │  │
│  │ • Chat Interface            │    │ • /api/analyze (POST)   │  │
│  │ • Real-time Log Display     │    │ • /health (GET)         │  │
│  │ • Report Rendering          │    │ • /api/routes (GET)     │  │
│  │                             │    │                         │  │
│  │ Port: 8501                  │    │ Port: 8000              │  │
│  │ (via streamlit run)          │    │ (via uvicorn)           │  │
│  └─────────────────────────────┘    └─────────────────────────┘  │
│                                              ▲                    │
│                                              │                    │
│                                    ┌─────────┴─────────┐         │
│                                    │                   │         │
│                        ┌───────────▼──────────┐       │         │
│                        │  ORCHESTRATOR (Graph)│       │         │
│                        │  orchestrator.py     │       │         │
│                        │                      │       │         │
│                        │ • Triage Node        │       │         │
│                        │ • Research Node      │◄──────┘         │
│                        │ • General Q Node     │                 │
│                        │ • Reporting Node     │                 │
│                        └──────────────────────┘                 │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘

Data Flow:
1. User enters query in Streamlit frontend
2. Frontend sends HTTP POST to /api/analyze
3. Backend receives request and builds state graph
4. Graph executes orchestrator logic
5. Backend captures all logs and execution results
6. Frontend receives response with logs and report
7. Frontend displays logs in real-time status container
8. Frontend renders final markdown report
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip or conda package manager
- Two terminal windows (one for backend, one for frontend)

### Step 1: Install Dependencies

```bash
# Navigate to project directory
cd c:\AI_Agents\corporate-intelligence-engine

# Install all required packages
pip install -r requirements.txt
```

**Required Packages:**
- `fastapi==0.109.0` - Web framework for backend
- `uvicorn==0.27.0` - ASGI server
- `streamlit==1.32.0` - Frontend framework
- `requests==2.31.0` - HTTP client for frontend
- `pydantic==2.6.1` - Data validation
- `langgraph==0.1.39` - State machine orchestration
- `python-multipart==0.0.6` - Form data handling

### Step 2: Verify Installation

```bash
# Check Python version
python --version

# Verify key packages
pip show fastapi streamlit uvicorn
```

## Running the Application

### Terminal 1: Start the FastAPI Backend

```bash
# Navigate to project directory
cd c:\AI_Agents\corporate-intelligence-engine

# Start the Uvicorn server with auto-reload
uvicorn backend:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
================================================================================
CORPORATE INTELLIGENCE ENGINE - FASTAPI BACKEND
================================================================================
Server started at: 2026-06-13T14:30:00.000000
Available endpoints:
  - POST /api/analyze
  - GET /health
  - GET /api/routes
  - GET /docs (API documentation)
================================================================================
```

**What to do next:** Keep this terminal running and open a new terminal for the frontend.

### Terminal 2: Start the Streamlit Frontend

```bash
# Open a NEW terminal window
# Navigate to project directory
cd c:\AI_Agents\corporate-intelligence-engine

# Start the Streamlit app
streamlit run frontend.py
```

**Expected Output:**
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501

  For better performance, install the Watchdog module:
    pip install watchdog
```

**The Streamlit app will automatically open in your default browser** at `http://localhost:8501`

---

## Using the Application

### 1. Check Backend Status

When you first load the frontend, check the sidebar to verify the backend is online:
- ✓ **Green checkmark** = Backend is running and healthy
- ✗ **Red X** = Backend is not accessible (start it in Terminal 1)

### 2. Enter a Query

In the chat input box at the bottom, type one of the following:

**Research Queries:**
```
Analyze the latest earnings for NVDA
Show me Tesla stock forecast
What's the current price of AAPL?
```

**General Questions:**
```
What are the top machine learning frameworks in 2024?
Explain quantitative analysis
What is a stock dividend?
```

### 3. View Real-Time Agent Activity

When you submit a query, you'll see:
1. **Your message** displayed in a chat bubble
2. **Status container** showing "Orchestrating AI Agents..."
3. **Agent execution trace** with logs from each step:
   - [ENTERING TRIAGE NODE]
   - LLM routing decision
   - [CONDITIONAL EDGE] path selection
   - [ENTERING RESEARCH/GENERAL_Q NODE]
   - Processing steps
4. **Status updates** to "Analysis Complete!"
5. **Final report** rendered in Markdown format

### 4. View Execution Metrics

Above the final report, you'll see:
- **Routing Decision**: Whether it was routed to Research or General Q
- **Execution Time**: Total time in milliseconds
- **Log Entries**: Number of captured log lines

---

## API Endpoints Documentation

### 1. Health Check

**Endpoint:** `GET /health`

**Description:** Check if the backend is running

**Response:**
```json
{
  "status": "healthy",
  "service": "corporate-intelligence-engine",
  "timestamp": "2026-06-13T14:30:00.000000"
}
```

---

### 2. Analyze (Main Endpoint)

**Endpoint:** `POST /api/analyze`

**Description:** Execute the orchestrator graph with user input

**Request Body:**
```json
{
  "user_input": "Analyze the latest earnings for NVDA"
}
```

**Response:**
```json
{
  "status": "success",
  "routing_decision": "research",
  "logs": [
    "[INFO] [ENTERING TRIAGE NODE]",
    "[INFO] User Input: Analyze the latest earnings for NVDA",
    "[INFO] Invoking LLM for structured routing decision...",
    "[INFO] LLM Response: {\"ticker\": \"NVDA\", ...}",
    "[INFO] [CONDITIONAL ROUTING] Decision: research",
    "[INFO] [CONDITIONAL EDGE] Taking RESEARCH path",
    "[INFO] [ENTERING RESEARCH NODE]",
    "[INFO] Research complete. 14 data points collected.",
    "[INFO] [REPORTING NODE COMPLETE]"
  ],
  "report_markdown": "# Financial Research Report: NVDA\n\n## Company Overview\n...",
  "error_message": "",
  "execution_time_ms": 245.3
}
```

---

### 3. Get Available Routes

**Endpoint:** `GET /api/routes`

**Description:** Get information about available routing paths

**Response:**
```json
{
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
```

---

### 4. API Documentation

**Access Interactive Docs:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Testing the API with curl

### Test 1: Health Check

```bash
curl http://localhost:8000/health
```

### Test 2: Analysis Request

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d "{\"user_input\": \"Analyze NVDA earnings\"}"
```

### Test 3: Get Routes

```bash
curl http://localhost:8000/api/routes
```

---

## Troubleshooting

### Issue: "Backend Connection Error" in Streamlit

**Solution:**
1. Ensure the FastAPI backend is running in Terminal 1
2. Verify it's running on `http://localhost:8000`
3. Reload the Streamlit page (Ctrl+R or Command+R)

### Issue: Backend won't start (Port 8000 already in use)

**Solution:**
```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID)
taskkill /PID <PID> /F

# Restart backend
uvicorn backend:app --reload
```

### Issue: Streamlit won't start (Port 8501 already in use)

**Solution:**
```bash
# Start on a different port
streamlit run frontend.py --server.port 8502
```

### Issue: "ModuleNotFoundError: No module named 'orchestrator'"

**Solution:**
Ensure you're running the commands from the project directory:
```bash
cd c:\AI_Agents\corporate-intelligence-engine
```

### Issue: Slow or hanging requests

**Solution:**
1. The orchestrator logs many messages; this is normal
2. Increase timeout in `frontend.py` if needed (currently 60 seconds)
3. Check that your system has sufficient resources

---

## Performance Metrics

### Typical Execution Times

| Component | Time (ms) |
|-----------|-----------|
| Triage Node | 5-10 |
| Research Node | 10-20 |
| Reporting Node | 5-10 |
| **Total (Research Path)** | **30-50** |
| **Total (General Q Path)** | **20-40** |

### Log Volume

- **Triage Node:** 10-15 log lines
- **Research Node:** 15-20 log lines
- **Reporting Node:** 5-10 log lines
- **Total:** 30-45 log lines per request

---

## Production Deployment

For production deployment, follow these steps:

### 1. Update Backend Configuration

**backend.py** changes:
```python
# Change CORS to restrict to your Streamlit domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Change reload to False
run(
    app,
    reload=False,  # Disable auto-reload in production
    log_level="info",
)
```

### 2. Update Frontend Configuration

**frontend.py** changes:
```python
# Change API URL to your production domain
API_BASE_URL = "https://api.yourdomain.com"
```

### 3. Deploy Backend

Using Gunicorn + Uvicorn:
```bash
pip install gunicorn
gunicorn backend:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 4. Deploy Frontend

Using Streamlit Cloud:
```bash
# Push your repo to GitHub
git push origin main

# Deploy via Streamlit Cloud (streamlit.io/cloud)
# Connect your GitHub repo
```

Or deploy to AWS/Azure/GCP using Docker:

**Dockerfile for Backend:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Development Workflow

### Hot Reload

Both FastAPI and Streamlit support hot reload:
- **Backend:** Changes to `backend.py` auto-reload (via `--reload`)
- **Frontend:** Changes to `frontend.py` auto-reload

Just save your changes and refresh the browser.

### Debugging

#### View Backend Logs

```bash
# Tail logs from the backend terminal
# All logs with [INFO], [ERROR], etc. are visible
```

#### View Frontend Logs

```bash
# Browser console (F12 or right-click → Inspect)
# Check for JavaScript errors

# Terminal where you ran streamlit:
# Streamlit debug messages
```

#### Enable Debug Mode

**backend.py:**
```python
run(
    app,
    log_level="debug",  # More verbose logging
)
```

---

## Architecture Components

### Backend (FastAPI)

**File:** `backend.py`

**Key Components:**
- `AnalysisRequest` - Request validation model
- `AnalysisResponse` - Response serialization model
- `LogCapture` - Custom logging handler to capture logs
- `/api/analyze` - Main analysis endpoint
- `build_graph()` - Imports and executes orchestrator

**Data Flow:**
```
HTTP POST /api/analyze
    ↓
Parse + Validate AnalysisRequest
    ↓
Build state graph from orchestrator.py
    ↓
Execute graph with user_input
    ↓
Capture all logs during execution
    ↓
Return AnalysisResponse with logs + report
    ↓
HTTP 200 + JSON response
```

### Frontend (Streamlit)

**File:** `frontend.py`

**Key Components:**
- Chat message display
- `st.chat_input()` - User query input
- `st.status()` - Real-time execution container
- `requests.post()` - API communication
- Markdown report rendering

**Data Flow:**
```
User types in chat input
    ↓
Display user message in chat
    ↓
Send POST request to /api/analyze
    ↓
Show status container "Orchestrating..."
    ↓
For each log line in response:
    Display log in status container
    ↓
Close status container with ✅
    ↓
Render final report_markdown
```

### Orchestrator (LangGraph)

**File:** `orchestrator.py`

**State Machine:**
```
START
  ↓
[Triage Node]
  ├─ Extracts ticker
  └─ Decides: research or general_q
  ↓
[Conditional Router]
  ├─→ [Research Node] → [Reporting Node] → END
  └─→ [General Q Node] → [Reporting Node] → END
```

---

## Next Steps & Enhancements

### Short Term

1. **Add file upload support**
   ```python
   # Allow users to upload CSV/PDF files for analysis
   uploaded_file = st.file_uploader("Upload data")
   ```

2. **Add export functionality**
   ```python
   # Export reports as PDF, DOCX
   st.download_button("Download Report", report_data)
   ```

3. **Add conversation history**
   ```python
   # Store analysis history in session
   # Allow multi-turn conversations
   ```

### Medium Term

4. **Real LLM integration**
   ```python
   # Replace mock routing with GPT-4
   # Use Anthropic structured output
   ```

5. **Financial data APIs**
   ```python
   # Connect to real APIs: yfinance, Alpha Vantage
   # Cache results with Redis
   ```

6. **Database persistence**
   ```python
   # Store analysis history
   # Track ticker analysis trends
   ```

### Long Term

7. **Multi-user support**
   ```python
   # User authentication
   # Separate workspaces per user
   ```

8. **Advanced analytics**
   ```python
   # Comparative analysis
   # Time-series forecasting
   # Sentiment analysis
   ```

9. **Monitoring & observability**
   ```python
   # LangSmith integration
   # Datadog metrics
   # Error tracking (Sentry)
   ```

---

## Support & Documentation

- **FastAPI Docs:** https://fastapi.tiangolo.com
- **Streamlit Docs:** https://docs.streamlit.io
- **LangGraph Docs:** https://python.langchain.com/en/latest/modules/agents/agent_executors/langgraph_document
- **Pydantic Docs:** https://docs.pydantic.dev

---

**Status:** ✅ Web Layer Complete  
**Built with:** FastAPI + Streamlit + LangGraph  
**Last Updated:** 2026-06-13
