# Local Development Setup Guide

Complete setup instructions for local development with proper environment configuration.

## Quick Setup (5 minutes)

### 1. Create Local Environment File

```bash
# Copy the template
cp .env.example .env

# Edit .env with your local settings
# For local development, most defaults are fine
```

### 2. Install Dependencies

```bash
# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
pip install pydantic-settings  # Required for config management
```

### 3. Start Backend

```bash
# Terminal 1
uvicorn backend:app --reload --port 8000
```

### 4. Start Frontend

```bash
# Terminal 2
streamlit run frontend.py --server.port 8501
```

### 5. Access Application

Open browser to: `http://localhost:8501`

---

## Environment Configuration

### Local .env File

Create a `.env` file in the project root with these settings:

```bash
# ============================================================================
# API CONFIGURATION
# ============================================================================
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_RELOAD=true
BACKEND_LOG_LEVEL=info

FRONTEND_HOST=localhost
FRONTEND_PORT=8501

API_REQUEST_TIMEOUT=60

# ============================================================================
# DEVELOPMENT SETTINGS
# ============================================================================
DEBUG=true
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:8501,http://localhost:3000

# ============================================================================
# LOGGING
# ============================================================================
LOG_LEVEL=DEBUG
LOG_FILE_PATH=logs/app.log

# ============================================================================
# AGENT CONFIGURATION
# ============================================================================
AGENT_MAX_ITERATIONS=10
AGENT_TIMEOUT=30

# ============================================================================
# APPLICATION SETTINGS
# ============================================================================
REPORT_FORMAT=markdown
REPORT_INCLUDE_CHARTS=true

# ============================================================================
# SECURITY (Development only - change for production)
# ============================================================================
SECRET_KEY=dev-secret-key-change-in-production
SECURE=false

# ============================================================================
# OPTIONAL: LLM INTEGRATION (for real LLM, uncomment and fill in)
# ============================================================================
# OPENAI_API_KEY=sk_test_...
# OPENAI_MODEL=gpt-4-turbo

# ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_MODEL=claude-3-opus-20240229

# ============================================================================
# OPTIONAL: DATABASE (for persistence)
# ============================================================================
# DATABASE_URL=postgresql://user:password@localhost:5432/corporate_intelligence
# REDIS_URL=redis://localhost:6379/0

# ============================================================================
# OPTIONAL: AWS (for cloud deployment)
# ============================================================================
# AWS_REGION=us-east-1
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
# S3_BUCKET_NAME=corporate-intelligence-reports

# ============================================================================
# OPTIONAL: MONITORING (for production)
# ============================================================================
# LANGSMITH_API_KEY=...
# LANGSMITH_PROJECT=corporate-intelligence-engine
# SENTRY_DSN=...
```

### ⚠️ Important Security Notes

1. **Never commit `.env`** - It's in `.gitignore`
2. **Always use `.env.example`** as template
3. **Never hardcode secrets** - Use environment variables
4. **For production**, use proper secret management:
   - AWS Secrets Manager
   - Azure Key Vault
   - HashiCorp Vault
   - Kubernetes Secrets

---

## Using Configuration in Code

### Access Configuration

```python
from config import settings

# Access any setting
print(settings.backend_port)        # 8000
print(settings.openai_api_key)      # None (if not set)
print(settings.environment)         # "development"
print(settings.is_development)      # True
print(settings.is_production)       # False
```

### Check if Optional Services are Configured

```python
from config import settings

if settings.has_openai:
    # Use OpenAI
    pass

if settings.has_database:
    # Connect to database
    pass

if settings.has_redis:
    # Use Redis cache
    pass
```

---

## Development Workflow

### 1. Making Changes

The backend automatically reloads on code changes (when `BACKEND_RELOAD=true`):

```bash
# Edit orchestrator.py
# Save the file
# Uvicorn automatically reloads
```

Streamlit also auto-reloads:

```bash
# Edit frontend.py
# Save the file
# Streamlit automatically reruns
```

### 2. Testing Changes

```bash
# Test backend
python test_backend.py

# Test specific endpoint
curl http://localhost:8000/health
```

### 3. Viewing Logs

```bash
# Tail log file
tail -f logs/app.log

# Or view in terminal where uvicorn is running
```

---

## Docker Development

### Build Images

```bash
# Build backend image
docker build -f docker/Dockerfile -t corporate-intelligence-backend .

# Build frontend image  
docker build -f docker/Dockerfile.frontend -t corporate-intelligence-frontend .
```

### Run with Docker Compose

```bash
# Start all services
docker-compose -f docker/docker-compose.yml up

# Start in background
docker-compose -f docker/docker-compose.yml up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop services
docker-compose down
```

---

## Adding LLM Integration

### OpenAI Setup

1. Get API key from https://platform.openai.com/api-keys
2. Add to `.env`:
   ```bash
   OPENAI_API_KEY=sk_test_your_key_here
   OPENAI_MODEL=gpt-4-turbo
   ```
3. In code:
   ```python
   from config import settings
   from openai import OpenAI
   
   client = OpenAI(api_key=settings.openai_api_key)
   ```

### Anthropic Setup

1. Get API key from https://console.anthropic.com
2. Add to `.env`:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-your_key_here
   ```
3. In code:
   ```python
   from config import settings
   from anthropic import Anthropic
   
   client = Anthropic(api_key=settings.anthropic_api_key)
   ```

---

## Database Setup (Optional)

### PostgreSQL

```bash
# Install (macOS)
brew install postgresql

# Install (Ubuntu)
sudo apt-get install postgresql postgresql-contrib

# Start service
psql postgres

# Create database
CREATE DATABASE corporate_intelligence;
```

Add to `.env`:
```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/corporate_intelligence
```

### Redis

```bash
# Install (macOS)
brew install redis

# Install (Ubuntu)
sudo apt-get install redis-server

# Start service
redis-server

# Test connection
redis-cli ping  # Should return PONG
```

Add to `.env`:
```bash
REDIS_URL=redis://localhost:6379/0
```

---

## VS Code Configuration

### Recommended Extensions

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "charliermarsh.ruff",
    "ms-python.black-formatter",
    "ms-python.debugpy",
    "httpyac.httpyac"
  ]
}
```

### Launch Configuration (.vscode/launch.json)

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Backend",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["backend:app", "--reload"],
      "jinja": true,
      "justMyCode": true
    },
    {
      "name": "Python: Tests",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/", "-v"],
      "jinja": true
    }
  ]
}
```

---

## Common Issues & Solutions

### Issue: Import Error - No module named 'config'

**Solution:**
```bash
# Ensure you're in the project root
cd c:\AI_Agents\corporate-intelligence-engine

# Install pydantic-settings
pip install pydantic-settings

# Verify PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Issue: Port 8000 already in use

**Solution:**
```bash
# Kill process using port 8000
lsof -ti:8000 | xargs kill -9  # macOS/Linux

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Use different port
uvicorn backend:app --port 8001
```

### Issue: `.env` file not loading

**Solution:**
```bash
# Verify .env exists in project root
ls -la .env

# Restart backend/frontend after creating .env
# Stop uvicorn and streamlit
# Start them again
```

### Issue: Streamlit can't connect to backend

**Solution:**
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check `CORS_ORIGINS` in `.env` includes `http://localhost:8501`
3. Reload frontend page

---

## Performance Tips

1. **Use PyPy** for faster Python execution
2. **Enable Redis** for caching queries
3. **Use PostgreSQL** instead of SQLite for production
4. **Profile with py-spy**: `pip install py-spy`
5. **Monitor with New Relic/DataDog** in production

---

## Next Steps

1. ✅ Create `.env` from `.env.example`
2. ✅ Install dependencies: `pip install -r requirements.txt`
3. ✅ Start backend: `uvicorn backend:app --reload`
4. ✅ Start frontend: `streamlit run frontend.py`
5. ✅ Test at `http://localhost:8501`
6. Make changes and see hot-reload in action
7. Add real LLM integration when ready
8. Set up database if needed
9. Deploy using Docker

---

## Getting Help

- Check [ARCHITECTURE.md](./ARCHITECTURE.md) for folder structure
- See [DEPLOYMENT.md](./DEPLOYMENT.md) for production setup
- Review [QUICKSTART.md](./QUICKSTART.md) for API usage
- Read configuration source: [config/settings.py](./config/settings.py)

---

**Status:** ✅ Development environment ready  
**Last Updated:** 2026-06-14
