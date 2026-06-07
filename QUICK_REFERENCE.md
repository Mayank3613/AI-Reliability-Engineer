# 🗂️ QUICK REFERENCE: EXTERNAL SERVICES & CREDENTIALS

One-page reference mapping all external services to where they're used in the code.

---

## 📍 CREDENTIAL LOCATION MAP

```
.env (root directory)
│
├── GCP_PROJECT_ID
│   └─ Used in: datastore_client.py, secret_manager.py
│
├── GOOGLE_APPLICATION_CREDENTIALS
│   └─ Used in: All Google Cloud services (auth)
│
├── GEMINI_API_KEY
│   ├─ Used in: agents/gemini_client.py (line 52)
│   ├─ File: aire/agents/gemini_client.py
│   └─ Usage: genai.configure(api_key=api_key)
│
├── DYNATRACE_ENVIRONMENT_ID
│   ├─ Used in: security/credentials.py, observability/*
│   ├─ Format: abc12345 (from abc12345.live.dynatrace.com)
│   └─ To Get: https://hub.cloud.dynatrace.com/
│
├── DYNATRACE_API_KEY
│   ├─ Used in: otel_setup.py, observability/dynatrace_client.py
│   ├─ Format: dt0c01.XXXX...
│   └─ To Get: Dynatrace Settings → API tokens
│
├── DT_OTLP_ENDPOINT
│   ├─ Used in: apps/otel_setup.py
│   ├─ Format: https://{DYNATRACE_ENVIRONMENT_ID}.live.dynatrace.com/api/v2/otlp
│   └─ Purpose: OTLP trace/metric export
│
└── BINDPLANE_API_KEY
    ├─ Used in: observability/telemetry_pipeline/
    └─ Purpose: Telemetry routing
```

---

## 🚀 EXTERNAL SERVICES AT A GLANCE

| Service | Credentials | Where Used | Purpose |
|---------|-------------|-----------|---------|
| **Google Cloud** | GCP_PROJECT_ID | All modules | Cloud infrastructure |
| | GOOGLE_APPLICATION_CREDENTIALS | All modules | GCP authentication |
| | GCP_REGION | deployments | Regional settings |
| **Gemini API** | GEMINI_API_KEY | agents/gemini_client.py | LLM inference |
| | GEMINI_MODEL | config | AI model selection |
| **Dynatrace** | DYNATRACE_ENVIRONMENT_ID | observability/* | Monitoring platform |
| | DYNATRACE_API_KEY | otel_setup.py | API authentication |
| | DT_OTLP_ENDPOINT | apps/otel_setup.py | Telemetry export |
| **BindPlane** | BINDPLANE_ENDPOINT | telemetry_pipeline/ | Telemetry router |
| | BINDPLANE_API_KEY | telemetry_pipeline/ | BindPlane auth |
| **Agent Search** | DATASTORE_ID | knowledge/datastore_client.py | Knowledge base |
| | AGENT_SEARCH_LOCATION | knowledge/* | Data location |

---

## 📂 FILE-BY-FILE CREDENTIAL REFERENCE

### [aire/agents/gemini_client.py](aire/agents/gemini_client.py)
**Requires:**
- `GEMINI_API_KEY` (line 52)
- `GEMINI_MODEL` (config)

**Does:**
- Initializes Gemini LLM client
- Configures safety settings
- Handles API calls with retry logic

**Error message if missing:**
```
EnvironmentError: GEMINI_API_KEY not set
```

---

### [aire/apps/otel_setup.py](aire/apps/otel_setup.py)
**Requires:**
- `DT_OTLP_ENDPOINT`
- `DT_API_TOKEN` (same as DYNATRACE_API_KEY)

**Does:**
- Sets up OpenTelemetry tracing
- Exports metrics to Dynatrace

**Error message if missing:**
```
EnvironmentError: DT_OTLP_ENDPOINT and DT_API_TOKEN must be set
```

---

### [aire/security/credentials.py](aire/security/credentials.py)
**Requires:**
- `GCP_PROJECT_ID`
- `DYNATRACE_ENVIRONMENT_ID`
- `DYNATRACE_API_KEY`
- `BINDPLANE_ENDPOINT`
- `BINDPLANE_API_KEY`

**Does:**
- Centralizes credential resolution
- Falls back from Secret Manager to env vars
- Validates all credentials are available

---

### [aire/security/secret_manager.py](aire/security/secret_manager.py)
**Requires:**
- `GCP_PROJECT_ID`
- `GOOGLE_APPLICATION_CREDENTIALS` (for auth)

**Does:**
- Fetches secrets from Google Cloud Secret Manager
- Used in production (if `USE_SECRET_MANAGER=true`)

---

### [aire/knowledge/datastore_client.py](aire/knowledge/datastore_client.py)
**Requires:**
- `GCP_PROJECT_ID`
- `AGENT_SEARCH_DATASTORE_ID`
- `GOOGLE_APPLICATION_CREDENTIALS` (for auth)

**Does:**
- Manages documents in Google Agent Search
- Upload/list/delete RAG documents

---

### [aire/observability/dynatrace_client.py](aire/observability/dynatrace_client.py)
**Requires:**
- `DYNATRACE_ENVIRONMENT_ID`
- `DYNATRACE_API_KEY`
- `DYNATRACE_BASE_URL`

**Does:**
- Queries Dynatrace metrics
- Fetches problem/incident data

---

---

## 🔄 SETUP FLOW

```
1. Create .env file
   ↓
2. Fill in GCP credentials
   ├─ GCP_PROJECT_ID
   ├─ GOOGLE_APPLICATION_CREDENTIALS
   └─ GCP_REGION
   ↓
3. Get Gemini API key
   └─ GEMINI_API_KEY
   ↓
4. Get Dynatrace credentials
   ├─ DYNATRACE_ENVIRONMENT_ID
   ├─ DYNATRACE_API_KEY
   ├─ DT_OTLP_ENDPOINT
   └─ DT_API_TOKEN
   ↓
5. Get BindPlane credentials (optional)
   ├─ BINDPLANE_ENDPOINT
   └─ BINDPLANE_API_KEY
   ↓
6. Verify all credentials
   └─ Run: python -m pytest aire/tests/
   ↓
7. Start application
   └─ python aire/services/main.py
```

---

## ✅ MINIMUM SETUP FOR LOCAL TESTING

**Required:**
```env
GCP_PROJECT_ID=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
GEMINI_API_KEY=AIzaSy...
DYNATRACE_ENVIRONMENT_ID=abc12345
DYNATRACE_API_KEY=dt0c01.XXXX...
DT_OTLP_ENDPOINT=https://abc12345.live.dynatrace.com/api/v2/otlp
DT_API_TOKEN=dt0c01.XXXX...
USE_SECRET_MANAGER=false
```

**Optional (can use defaults):**
- `BINDPLANE_*` (only needed for telemetry routing)
- `AGENT_SEARCH_*` (only needed for RAG)
- Database URLs (only if using persistence)

---

## 🔗 CREDENTIAL SOURCES (WHERE TO GET THEM)

| Credential | Service | URL | Steps |
|-----------|---------|-----|-------|
| GCP_PROJECT_ID | Google Cloud | https://console.cloud.google.com/ | Select project → Copy ID |
| GOOGLE_APPLICATION_CREDENTIALS | GCP Service Account | https://console.cloud.google.com/iam-admin/serviceaccounts | Create SA → Download JSON |
| GEMINI_API_KEY | Google AI Studio | https://aistudio.google.com/apikey | Create API Key |
| DYNATRACE_ENVIRONMENT_ID | Dynatrace | https://hub.cloud.dynatrace.com/ | Select env → Extract ID from URL |
| DYNATRACE_API_KEY | Dynatrace API Tokens | https://YOUR_ENV.live.dynatrace.com/ui/settings/integration/apiTokens | Create token with required scopes |
| BINDPLANE_ENDPOINT | BindPlane | Your BindPlane deployment | Contact platform team |
| BINDPLANE_API_KEY | BindPlane | BindPlane UI → Settings | Generate API key |

---

## 🚨 VALIDATION SCRIPT

Run this to check all credentials:

```bash
python -c "
import os
from dotenv import load_dotenv

load_dotenv('.env')

required = {
    'GCP_PROJECT_ID': 'GCP',
    'GEMINI_API_KEY': 'Gemini',
    'DYNATRACE_API_KEY': 'Dynatrace',
    'DYNATRACE_ENVIRONMENT_ID': 'Dynatrace',
}

print('Credential Status:')
for var, service in required.items():
    status = '✅' if os.getenv(var) else '❌'
    print(f'{status} {var} ({service})')
"
```

---

## 📋 PRODUCTION DEPLOYMENT

For Cloud Run, use Google Cloud Secret Manager instead of .env:

```bash
# Create secrets
gcloud secrets create aire-gemini-api-key --data-file=- <<< "AIzaSy..."
gcloud secrets create aire-dynatrace-api-key --data-file=- <<< "dt0c01..."

# Deploy with secret references
gcloud run deploy aire-backend \
  --source . \
  --set-env-vars GCP_PROJECT_ID=my-project \
  --secret GEMINI_API_KEY=aire-gemini-api-key:latest \
  --secret DYNATRACE_API_KEY=aire-dynatrace-api-key:latest
```

---

## 🆘 TROUBLESHOOTING

| Problem | Cause | Fix |
|---------|-------|-----|
| ImportError: google.generativeai | Package not installed | `pip install google-generativeai` |
| EnvironmentError: GEMINI_API_KEY not set | Missing .env file | Create `.env` and fill credentials |
| 403 Forbidden from Dynatrace | Wrong API token | Check scopes: metrics.read, traces.read |
| Connection refused to DT endpoint | Wrong environment ID | Copy ID from your environment URL |
| PermissionDenied in Secret Manager | Missing permissions | Add `Secret Manager Secret Accessor` role |

---

**Document version:** 1.0 (2026-06-07)
**Project:** AIRE - AI Reliability Engine

For detailed setup, see [EXTERNAL_REQUIREMENTS.md](./EXTERNAL_REQUIREMENTS.md) or [SETUP_CHECKLIST.md](./SETUP_CHECKLIST.md)
