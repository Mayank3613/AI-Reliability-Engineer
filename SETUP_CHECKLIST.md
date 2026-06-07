# ⚡ AIRE SETUP CHECKLIST

Quick reference for getting AIRE up and running.

---

## 📋 PRE-FLIGHT CHECKLIST

- [ ] Python 3.9+ installed
- [ ] Git installed
- [ ] GCP account with a project
- [ ] Dynatrace account (free trial: https://www.dynatrace.com/)
- [ ] Internet connection (for API calls)

---

## 🔑 STEP 1: Gather External Credentials (15-20 minutes)

### 1.1 Google Cloud Platform
- [ ] Create GCP project: https://console.cloud.google.com/
- [ ] Copy **Project ID** → Save as `GCP_PROJECT_ID`
- [ ] Create Service Account:
  - Go to: https://console.cloud.google.com/iam-admin/serviceaccounts
  - Click "Create Service Account"
  - Name: `aire-dev`
  - Grant roles:
    - [ ] Vertex AI User
    - [ ] Cloud Datastore User
    - [ ] Datastore User
    - [ ] Secret Manager Secret Accessor
    - [ ] Cloud Run Developer
  - Click "Create and Continue"
  - Create JSON key → Download and save as `service-account-key.json`
  - Copy full path → Save as `GOOGLE_APPLICATION_CREDENTIALS`

### 1.2 Gemini API
- [ ] Go to: https://aistudio.google.com/apikey
- [ ] Click "Create API Key"
- [ ] Select your GCP project
- [ ] Copy key → Save as `GEMINI_API_KEY`

### 1.3 Dynatrace
- [ ] Sign up: https://www.dynatrace.com/ (free trial)
- [ ] Create environment or access existing one
- [ ] Go to Settings → Integration → API tokens
- [ ] Create new token named `AIRE_DEV` with scopes:
  - [ ] metrics.read
  - [ ] traces.read
  - [ ] logs.read
  - [ ] otlp.ingest
- [ ] Copy token → Save as `DYNATRACE_API_KEY`
- [ ] Extract **Environment ID** from URL (e.g., `abc12345` from `abc12345.live.dynatrace.com`)
- [ ] Save as `DYNATRACE_ENVIRONMENT_ID`

### 1.4 BindPlane (Optional for local dev)
- [ ] Skip for now (or deploy: https://docs.bindplane.bluemedora.com/)
- [ ] Save dummy credentials for testing

---

## 📝 STEP 2: Create `.env` File

```bash
# Navigate to project root
cd c:\Users\prana\SevenEyes

# Copy template
cp .env.example .env

# Edit with your credentials
notepad .env
```

**Minimum required values:**

```env
# GCP
GCP_PROJECT_ID=your-actual-gcp-project-id
GCP_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\service-account-key.json
VERTEX_AI_LOCATION=us-central1

# Gemini
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GEMINI_MODEL=gemini-2.0-flash
GEMINI_PRO_MODEL=gemini-1.5-pro

# Dynatrace
DYNATRACE_ENVIRONMENT_ID=abc12345
DYNATRACE_API_KEY=dt0c01.XXXXXXXXXXXXXXXXXXXXXXXX
DT_OTLP_ENDPOINT=https://abc12345.live.dynatrace.com/api/v2/otlp
DT_API_TOKEN=dt0c01.XXXXXXXXXXXXXXXXXXXXXXXX

# Development
USE_SECRET_MANAGER=false
ENVIRONMENT=development
OTEL_SERVICE_NAME=aire-backend
PORT=8080
LOG_LEVEL=INFO
```

---

## ✅ STEP 3: Verify Credentials

```bash
# Load environment
$env:PYTHONPATH = "$env:PYTHONPATH;C:\Users\prana\SevenEyes"

# Run verification script
python -c "
import os
from dotenv import load_dotenv

load_dotenv('.env')

print('=== AIRE Credential Verification ===\n')

checks = {
    'GCP_PROJECT_ID': 'GCP Project ID',
    'GEMINI_API_KEY': 'Gemini API Key',
    'DYNATRACE_ENVIRONMENT_ID': 'Dynatrace Environment ID',
    'DYNATRACE_API_KEY': 'Dynatrace API Token',
    'GOOGLE_APPLICATION_CREDENTIALS': 'GCP Service Account Path',
}

failed = []
for env_key, display_name in checks.items():
    value = os.getenv(env_key)
    if value:
        # Hide sensitive values
        if 'KEY' in env_key or 'TOKEN' in env_key:
            display = '✓ SET'
        else:
            display = f'✓ {value}'
        print(f'✅ {display_name}: {display}')
    else:
        print(f'❌ {display_name}: NOT SET')
        failed.append(display_name)

print()
if failed:
    print(f'⚠️  Missing {len(failed)} credential(s): {', '.join(failed)}')
    print('👉 See EXTERNAL_REQUIREMENTS.md for setup help')
else:
    print('✨ All credentials verified!')
"
```

---

## 📦 STEP 4: Install Dependencies

```bash
# Navigate to project
cd c:\Users\prana\SevenEyes

# Install Python packages
pip install -r aire/requirements.txt

# Verify installation
pip list | grep -E 'google-generativeai|opentelemetry|pydantic'
```

**Expected output:**
```
google-generativeai    0.4.0+
google-cloud-aiplatform 1.26.0+
opentelemetry-api      1.15.0+
pydantic               2.0.0+
```

---

## 🚀 STEP 5: Run the Application

### Option A: Test Gemini API Connection
```bash
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

# Test Gemini connectivity
from aire.agents.gemini_client import GeminiClient

try:
    client = GeminiClient(model_name='gemini-1.5-pro')
    response = client.generate('Say hello to AIRE!')
    print(f'✨ Gemini Response: {response}')
except Exception as e:
    print(f'❌ Error: {e}')
"
```

### Option B: Run Services
```bash
# Start the main service
python aire/services/main.py

# Expected output:
# INFO: AIRE Backend Started
# INFO: Listening on http://localhost:8080
```

### Option C: Run Tests
```bash
# Run unit tests
pytest aire/tests/ -v

# Run with coverage
pytest aire/tests/ --cov=aire --cov-report=html
```

---

## 🐳 STEP 6: Docker Setup (Optional)

```bash
# Build Docker image
docker build -f aire/services/Dockerfile -t aire:latest .

# Run container
docker run -p 8080:8080 --env-file .env aire:latest

# Or use Docker Compose
docker-compose up
```

---

## 🌐 STEP 7: Test API Endpoints

```bash
# Health check
curl http://localhost:8080/health

# Test Reliability Agent
curl -X POST http://localhost:8080/api/agents/reliability \
  -H "Content-Type: application/json" \
  -d '{"incident": "High P95 latency detected"}'

# Test Cost Analysis
curl -X POST http://localhost:8080/api/agents/cost \
  -H "Content-Type: application/json" \
  -d '{"timeframe": "last_month"}'
```

---

## 🔍 STEP 8: Monitor & Debug

### View Logs
```bash
# Local logs
tail -f aire/logs/aire.log

# Check Dynatrace dashboard
# Navigate to: https://abc12345.live.dynatrace.com (Dynatrace environment)
```

### Verify Telemetry
```python
# Check what's being exported to Dynatrace
python -c "
from aire.apps.otel_setup import setup_otel
tracer, meter = setup_otel('aire-test')
print('✅ OpenTelemetry configured')
print(f'   Service: aire-test')
print(f'   Endpoint: {os.getenv(\"OTEL_EXPORTER_OTLP_ENDPOINT\")}')
"
```

---

## 🚨 TROUBLESHOOTING

### Issue: "GEMINI_API_KEY not set"
**Solution:** Make sure `.env` is in the project root and `GEMINI_API_KEY=...` is filled in.
```bash
ls -la .env  # Check file exists
grep GEMINI .env  # Check it's set
```

### Issue: "GCP authentication failed"
**Solution:** Verify service account key file path and permissions.
```bash
# Check file exists and is readable
cat "$GOOGLE_APPLICATION_CREDENTIALS" | head -5

# Or use gcloud auth
gcloud auth application-default login
```

### Issue: "Dynatrace connection refused"
**Solution:** Check environment ID and API token.
```bash
# Test connectivity
curl -I "https://$DYNATRACE_ENVIRONMENT_ID.live.dynatrace.com"

# Verify API token has correct permissions
# Go to: https://docs.dynatrace.com/docs/platform/platform-services/user-management/api-tokens
```

### Issue: "Port 8080 already in use"
**Solution:** Change port in `.env`
```env
PORT=8081  # Use different port
```

---

## 📚 NEXT STEPS

1. **Read documentation:**
   - [EXTERNAL_REQUIREMENTS.md](./EXTERNAL_REQUIREMENTS.md) - Detailed credential setup
   - [aire/README.md](./aire/README.md) - Project architecture

2. **Explore code:**
   - [aire/agents/gemini_client.py](./aire/agents/gemini_client.py) - LLM client
   - [aire/apps/](./aire/apps/) - Agent implementations
   - [aire/dashboard/](./aire/dashboard/) - React UI

3. **Deploy to production:**
   - See [aire/deploy/README.md](./aire/deploy/) for Cloud Run deployment
   - Use Google Cloud Secret Manager for credentials

---

## 📞 GETTING HELP

| Issue | Resource |
|-------|----------|
| GCP Setup | https://cloud.google.com/docs/authentication/gcloud-sa |
| Gemini API | https://ai.google.dev/docs |
| Dynatrace | https://docs.dynatrace.com/ |
| OpenTelemetry | https://opentelemetry.io/docs/ |
| Project Docs | EXTERNAL_REQUIREMENTS.md |

---

## ✨ YOU'RE ALL SET!

Once you complete these steps, you have:
- ✅ All external credentials configured
- ✅ Python environment ready
- ✅ Dependencies installed
- ✅ Application deployable

**Happy coding! 🚀**

---

**Last Updated:** 2026-06-07
**Project:** AIRE - AI Reliability Engine
