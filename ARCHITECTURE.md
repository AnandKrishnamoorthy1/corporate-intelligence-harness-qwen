# Project Architecture & Folder Structure

## Production-Grade Architecture

This project follows enterprise-level best practices for AI applications with clear separation of concerns, secure configuration management, and Docker containerization.

```
corporate-intelligence-engine/
│
├── 📄 Root Configuration Files
│   ├── .env                    # ⚠️ NEVER COMMIT - Local environment variables
│   ├── .env.example            # ✓ Safe template - version controlled
│   ├── requirements.txt        # Python dependencies
│   ├── .gitignore             # Prevents accidental commits
│   ├── README.md              # Project overview
│   ├── QUICKSTART.md          # Setup instructions
│   ├── DEPLOYMENT.md          # Production deployment guide
│   ├── ARCHITECTURE.md        # This file
│   └── LICENSE
│
├── 📁 config/                 # ⚙️ CONFIGURATION MANAGEMENT
│   ├── __init__.py           # Package init
│   ├── settings.py           # Pydantic settings with env var loading
│   └── README.md             # Configuration guide
│
├── 📁 app/                    # 🧠 MAIN APPLICATION CODE
│   ├── __init__.py           # Package init
│   │
│   ├── 📁 models/            # 📊 PYDANTIC MODELS & SCHEMAS
│   │   ├── __init__.py       # Exports all models
│   │   └── README.md         # Model documentation
│   │   # Future:
│   │   # ├── agent_state.py  # State machine models
│   │   # └── llm_schemas.py  # LLM structured output schemas
│   │
│   ├── 📁 api/               # 🌐 REST API ENDPOINTS
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app initialization
│   │   ├── routes.py         # Endpoint definitions (future)
│   │   └── README.md
│   │   # Future:
│   │   # ├── health.py       # Health check endpoints
│   │   # ├── analysis.py     # Analysis endpoints
│   │   # └── webhooks.py     # Webhook endpoints
│   │
│   ├── 📁 orchestrator/      # 🤖 STATE MACHINE & AGENTS
│   │   ├── __init__.py
│   │   ├── graph.py          # LangGraph state machine
│   │   ├── nodes.py          # Node implementations
│   │   └── README.md
│   │   # Future:
│   │   # ├── triage_node.py  # Router node
│   │   # ├── research_node.py
│   │   # ├── general_q_node.py
│   │   # └── reporting_node.py
│   │
│   ├── 📁 prompts/           # 📝 LLM SYSTEM PROMPTS
│   │   ├── __init__.py
│   │   ├── system_prompts.py # System message templates
│   │   └── README.md
│   │   # Future:
│   │   # ├── triage.txt
│   │   # ├── research.txt
│   │   # └── general_qa.txt
│   │
│   └── 📁 utils/             # 🛠️ UTILITY FUNCTIONS (future)
│       ├── __init__.py
│       ├── logging.py        # Logging configuration
│       └── cache.py          # Caching utilities
│
├── 📁 docker/                # 🐳 CONTAINERIZATION
│   ├── Dockerfile            # Backend container
│   ├── Dockerfile.frontend   # Frontend container
│   ├── docker-compose.yml    # Multi-container orchestration
│   └── README.md             # Docker deployment guide
│
├── 📁 tests/                 # ✅ TESTING
│   ├── __init__.py
│   ├── test_backend.py       # Backend unit/integration tests
│   ├── test_frontend.py      # Frontend tests (future)
│   └── conftest.py           # Pytest fixtures (future)
│
├── 📁 logs/                  # 📋 APPLICATION LOGS (generated)
│   └── app.log              # Generated at runtime
│
├── 📄 Root Application Files (Entry Points)
│   ├── backend.py            # FastAPI application entry point
│   ├── frontend.py           # Streamlit application entry point
│   ├── orchestrator.py       # State machine (to be moved to app/orchestrator/)
│   └── test_backend.py       # Backend tests
│
└── 📁 docs/                  # 📚 DOCUMENTATION (future)
    ├── API.md                # API documentation
    ├── AGENTS.md             # Agent architecture
    └── CONTRIBUTING.md       # Contribution guidelines
```

---

## Folder Structure Explanation

### 1. **Root Level** 🏠
Files at the root for quick access to essential project information and entry points.

**What goes here:**
- Entry point scripts (`backend.py`, `frontend.py`)
- Main configuration files (`.env`, `requirements.txt`)
- Documentation (`README.md`, `QUICKSTART.md`)
- Project metadata (`LICENSE`, `.gitignore`)

**Why:**
- Quick identification of project type
- Easy setup for developers
- Standard Python project layout

---

### 2. **config/** ⚙️
**Purpose:** Centralized environment and configuration management.

**Current files:**
- `settings.py` - Pydantic BaseSettings for environment variables

**Best practices:**
- ✅ Uses Pydantic for validation
- ✅ Environment variables via `.env` file
- ✅ Defaults for development, overrides for production
- ✅ Never commit actual `.env` (only `.env.example`)
- ✅ Type-safe configuration access

**Usage:**
```python
from config import settings

print(settings.openai_api_key)  # Loaded from .env or env var
print(settings.backend_port)    # Loaded or uses default
```

---

### 3. **app/** 🧠
**Purpose:** Main application code organized by function.

#### **app/models/** 📊
Pydantic models for:
- Request/response validation
- Database schemas (future)
- LLM structured output schemas

```python
from app.models import AnalysisRequest, AnalysisResponse
```

#### **app/api/** 🌐
FastAPI routes and endpoints:
- Currently in `backend.py` (should move here)
- Health checks, analysis endpoints, webhooks
- Request validation and error handling

```python
from fastapi import FastAPI
app = FastAPI()

@app.post("/api/analyze")
def analyze(request: AnalysisRequest):
    ...
```

#### **app/orchestrator/** 🤖
LangGraph state machine and agents:
- `graph.py` - State machine definition
- `nodes.py` - Individual node implementations
- Each node is a pure function
- Deterministic execution flow

```python
from app.orchestrator import build_graph

graph = build_graph()
result = graph.invoke(initial_state)
```

#### **app/prompts/** 📝
System prompts for LLM agents:
- Triage/routing prompts
- Research analysis prompts
- General QA prompts
- System messages

```python
from app.prompts import TRIAGE_PROMPT, RESEARCH_PROMPT

prompt = TRIAGE_PROMPT.format(user_input="Analyze NVDA")
```

---

### 4. **docker/** 🐳
**Purpose:** Containerization for local and production deployment.

**Files:**
- `Dockerfile` - Backend container
- `Dockerfile.frontend` - Frontend container  
- `docker-compose.yml` - Multi-container orchestration
  - Backend service
  - Frontend service
  - Redis service (optional, for caching)

**Usage:**
```bash
# Local development
docker-compose up

# Production
docker-compose -f docker-compose.yml up -d
```

---

### 5. **tests/** ✅
**Purpose:** Test suite for all components.

**Current:**
- `test_backend.py` - Backend API tests

**Future:**
- `test_orchestrator.py` - State machine tests
- `test_frontend.py` - Frontend UI tests
- `conftest.py` - Pytest fixtures

---

### 6. **logs/** 📋
**Purpose:** Application logs (generated at runtime).

**Contents:**
- `app.log` - Main application logs
- Never committed to version control

---

## Environment Configuration Strategy

### Development (.env.local)
```bash
# .env.local (never commit)
ENVIRONMENT=development
DEBUG=true
OPENAI_API_KEY=sk_test_your_key
```

### Template (.env.example)
```bash
# .env.example (ALWAYS commit this)
ENVIRONMENT=development
DEBUG=false
OPENAI_API_KEY=your_key_here
```

### Production (.env in secret manager)
```bash
# Store in AWS Secrets Manager, Azure KeyVault, etc.
ENVIRONMENT=production
DEBUG=false
OPENAI_API_KEY=sk_live_your_key
```

---

## Import Patterns

### ✅ Recommended Imports

**From config:**
```python
from config import settings
```

**From models:**
```python
from app.models import AnalysisRequest, AnalysisResponse
```

**From orchestrator:**
```python
from app.orchestrator import build_graph
```

**From prompts:**
```python
from app.prompts import TRIAGE_PROMPT, RESEARCH_PROMPT
```

### ❌ Avoid

```python
# Don't do this
import sys
sys.path.insert(0, '/some/weird/path')
```

---

## Adding New Features

### Add a new agent node:
1. Create `app/orchestrator/my_node.py`
2. Define node function with state validation
3. Add to `app/orchestrator/__init__.py` exports
4. Add to graph in `app/orchestrator/graph.py`

### Add a new API endpoint:
1. Create `app/api/my_route.py`
2. Define request/response models in `app/models/`
3. Add route to `backend.py` or create route handler
4. Test in `tests/test_backend.py`

### Add new prompts:
1. Add to `app/prompts/system_prompts.py`
2. Export in `app/prompts/__init__.py`
3. Use in agent nodes

---

## Production Checklist

- [ ] `.env` file created from `.env.example`
- [ ] All required API keys configured
- [ ] Database URL configured (if using)
- [ ] Redis URL configured (if caching)
- [ ] Docker images built and tested
- [ ] Docker compose tested locally
- [ ] Logs directory writable
- [ ] CORS origins configured correctly
- [ ] SSL certificates configured (if HTTPS)
- [ ] Monitoring/alerting configured

---

## Security Best Practices

✅ **DO:**
- Store all secrets in `.env` (not committed)
- Use `config/settings.py` for all configuration
- Never log sensitive data
- Validate all inputs with Pydantic
- Use environment-specific configs
- Rotate API keys regularly
- Use HTTPS in production

❌ **DON'T:**
- Commit `.env` files to git
- Hardcode API keys
- Use default/weak secrets in production
- Log user data or financial information
- Expose internal error messages
- Trust user input without validation

---

## References

- [12-Factor App Methodology](https://12factor.net/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/api/pydantic_settings/)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/deployment/)
- [Python Project Structure](https://docs.python-guide.org/writing/structure/)

---

**Status:** ✅ Production-ready architecture  
**Last Updated:** 2026-06-14
