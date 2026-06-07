# AIRE External Requirements & Configuration Guide

This document lists all external APIs, platforms, and credentials required to run the AIRE project, and where to configure them.

---

## 🔑 WHERE TO PUT CREDENTIALS

### **Option 1: Local Development (Recommended)**
Create a `.env` file in the root directory:
```bash
cp aire/security/.env.example .env
# Then edit .env and fill in your credentials
```

**File Location:**
```
c:\Users\prana\SevenEyes\.env
```

### **Option 2: Production (Google Cloud Secret Manager)**
Set `USE_SECRET_MANAGER=true` in your environment, and upload all secrets to Google Cloud Secret Manager. The app will automatically fetch them.

---

## 📋 EXTERNAL SERVICES & CREDENTIALS NEEDED

### 1. **Google Cloud Platform (GCP)**

**Required for:**
- Vertex AI / Gemini API access
- Google Cloud Datastore
- Agent Search (Discovery Engine)
- Secret Manager
- Cloud Run deployment

**Credentials to obtain:**

| Variable | Description | Where to Get | Format |
|----------|-------------|--------------|--------|
| `GCP_PROJECT_ID` | Your GCP project ID | [GCP Console](https://console.cloud.google.com/) → Select Project | `my-project-id` |
| `GCP_REGION` | GCP region for services | [GCP Console](https://console.cloud.google.com/) | `us-central1`, `us-east1`, etc. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account JSON key path | [Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts) → Create SA → Download JSON | `/path/to/service-account-key.json` |

**Setup steps:**
1. Create a GCP project: https://console.cloud.google.com/
2. Create a service account with these roles:
   - `Vertex AI User`
   - `Cloud Datastore User`
   - `Datastore User`
   - `Secret Manager Secret Accessor`
   - `Cloud Run Developer`
3. Create and download a JSON key from the service account
4. Set the path: `export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"`

**Add to `.env`:**
```env
GCP_PROJECT_ID=my-gcp-project-id
GCP_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
VERTEX_AI_LOCATION=us-central1
```

---

### 2. **Google Gemini API** (AI Model)

**Required for:**
- All LLM calls (agents, chat, analysis)
- Response generation for reliability, cost, and recommendation agents

**Credentials to obtain:**

| Variable | Description | Where to Get | Format |
|----------|-------------|--------------|--------|
| `GEMINI_API_KEY` | Gemini API key (optional - use Application Default Credentials in production) | [Google AI Studio](https://aistudio.google.com/apikey) | `AIzaSy...` |
| `GEMINI_MODEL` | Flash model name | Hardcoded | `gemini-2.0-flash` |
| `GEMINI_PRO_MODEL` | Pro model name | Hardcoded | `gemini-1.5-pro` |

**Setup steps:**
1. Go to https://aistudio.google.com/apikey
2. Click "Create API Key" → Select your GCP project
3. Copy the API key

**In Production (Recommended):**
- Use Google Cloud Application Default Credentials (ADC) via Service Account
- No need to set `GEMINI_API_KEY` explicitly

**Add to `.env`:**
```env
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GEMINI_MODEL=gemini-2.0-flash
GEMINI_PRO_MODEL=gemini-1.5-pro
```

---

### 3. **Dynatrace** (Observability Platform)

**Required for:**
- Tracing and telemetry collection
- Metrics export
- Monitoring LLM calls
- Alert management

**Credentials to obtain:**

| Variable | Description | Where to Get | Format |
|----------|-------------|--------------|--------|
| `DYNATRACE_ENVIRONMENT_ID` | Your Dynatrace environment ID | [Dynatrace Hub](https://hub.cloud.dynatrace.com/) → Select environment | `abc12345` |
| `DYNATRACE_API_KEY` | API token for programmatic access | [Dynatrace Settings](https://docs.dynatrace.com/docs/platform/platform-services/user-management/api-tokens) → Create Token | `dt0c01.XXXXXXXXXX...` |
| `DT_OTLP_ENDPOINT` | OTLP export endpoint | Based on your environment | `https://abc12345.live.dynatrace.com/api/v2/otlp` |
| `DT_API_TOKEN` | Same as `DYNATRACE_API_KEY` (alternative name) | Same as above | `dt0c01.XXXXXXXXXX...` |

**Setup steps:**
1. Sign up at https://www.dynatrace.com/
2. Create a Dynatrace environment or use existing one
3. Go to **Settings → Integration → API tokens**
4. Create a new token with these scopes:
   - `metrics.read`
   - `traces.read`
   - `logs.read`
   - `otlp.ingest` (for OTLP endpoint)
5. Copy the environment ID from the URL (e.g., `abc12345.live.dynatrace.com`)

**Add to `.env`:**
```env
DYNATRACE_ENVIRONMENT_ID=abc12345
DYNATRACE_API_KEY=dt0c01.XXXXXXXXXX...
DT_OTLP_ENDPOINT=https://abc12345.live.dynatrace.com/api/v2/otlp
DT_API_TOKEN=dt0c01.XXXXXXXXXX...
ALERT_EMAIL=your-email@example.com
```

---

### 4. **BindPlane** (Telemetry Router)

**Required for:**
- Routing telemetry data to multiple backends
- Data transformation pipeline

**Credentials to obtain:**

| Variable | Description | Where to Get | Format |
|----------|-------------|--------------|--------|
| `BINDPLANE_ENDPOINT` | BindPlane API server URL | Your BindPlane deployment | `https://your-bindplane-server:3001` |
| `BINDPLANE_API_KEY` | Authentication token | BindPlane UI → Settings | API key string |

**Setup steps:**
1. Deploy BindPlane (self-hosted or via cloud) or get URL from your platform team
2. Generate an API key in BindPlane UI
3. Note the server endpoint (default port: 3001)

**Add to `.env`:**
```env
BINDPLANE_ENDPOINT=https://your-bindplane-server:3001
BINDPLANE_API_KEY=your-bindplane-api-key
```

---

### 5. **Google Agent Search / Discovery Engine**

**Required for:**
- Document storage (RAG knowledge base)
- Semantic search over documents
- Agent context retrieval

**Credentials to obtain:**

| Variable | Description | Where to Get | Format |
|----------|-------------|--------------|--------|
| `AGENT_SEARCH_LOCATION` | Datastore location | [Vertex AI Search](https://console.cloud.google.com/vertex-ai/search) | `global` |
| `DATASTORE_ID` / `AGENT_SEARCH_DATASTORE_ID` | Datastore ID for documents | Create in Vertex AI Search console | `aire-knowledge-store` |
| `SEARCH_ENGINE_ID` | (Optional) Search engine ID | Vertex AI Search console | Engine ID string |

**Setup steps:**
1. Go to [Vertex AI Search & Conversation](https://console.cloud.google.com/vertex-ai/search)
2. Create a new Datastore
3. Configure it with your documents
4. Copy the Datastore ID

**Add to `.env`:**
```env
AGENT_SEARCH_LOCATION=global
DATASTORE_ID=aire-knowledge-store
SEARCH_ENGINE_ID=aire-search-engine
```

---

### 6. **Google Cloud Text Embeddings**

**Required for:**
- Converting documents to vector embeddings
- Semantic similarity matching

**Credentials:**
- Uses GCP credentials (already configured via `GOOGLE_APPLICATION_CREDENTIALS`)

| Variable | Description | Format |
|----------|-------------|--------|
| `EMBEDDING_MODEL` | Model to use for embeddings | `text-embedding-004` |

**Add to `.env`:**
```env
EMBEDDING_MODEL=text-embedding-004
```

---

### 7. **OpenTelemetry OTLP Endpoint**

**Required for:**
- Sending traces and metrics to collectors
- Dynatrace or other OTLP-compatible backend

| Variable | Description | Example |
|----------|-------------|---------|
| `OTEL_SERVICE_NAME` | Service name in traces | `aire-backend` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint | `https://abc12345.live.dynatrace.com/api/v2/otlp` |
| `OTEL_EXPORTER_OTLP_HEADERS` | Headers for authentication | `Authorization=Api-Token <token>` |

**Add to `.env`:**
```env
OTEL_SERVICE_NAME=aire-backend
OTEL_EXPORTER_OTLP_ENDPOINT=https://abc12345.live.dynatrace.com/api/v2/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Api-Token dt0c01.XXXXXXXXXX...
```

---

## 🗂️ FILE LOCATIONS WHERE CREDENTIALS ARE USED

| File | Purpose | Credentials Used |
|------|---------|------------------|
| [aire/agents/gemini_client.py](aire/agents/gemini_client.py) | LLM API calls | `GEMINI_API_KEY` |
| [aire/apps/otel_setup.py](aire/apps/otel_setup.py) | Telemetry export | `DT_OTLP_ENDPOINT`, `DT_API_TOKEN` |
| [aire/security/credentials.py](aire/security/credentials.py) | Credential resolution | All of the above |
| [aire/security/secret_manager.py](aire/security/secret_manager.py) | Cloud Secret Manager | `GCP_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` |
| [aire/knowledge/datastore_client.py](aire/knowledge/datastore_client.py) | Document storage | `GCP_PROJECT_ID`, `DATASTORE_ID`, `GOOGLE_APPLICATION_CREDENTIALS` |
| [aire/observability/dynatrace_config.yaml](aire/observability/dynatrace_config.yaml) | Observability config | `DYNATRACE_ENVIRONMENT_ID`, `DYNATRACE_API_KEY` |
| [aire/observability/telemetry_pipeline/bindplane_config.yaml](aire/observability/telemetry_pipeline/bindplane_config.yaml) | Telemetry routing | `BINDPLANE_ENDPOINT`, `BINDPLANE_API_KEY` |

---

## ⚙️ SETUP CHECKLIST

### ✅ Step 1: Create `.env` File
```bash
cd c:\Users\prana\SevenEyes
cp aire/security/.env.example .env
```

### ✅ Step 2: Fill in All Credentials

**Minimum Required (for local testing):**
```env
# Google Cloud
GCP_PROJECT_ID=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Gemini (optional - can use GCP ADC)
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# Dynatrace
DYNATRACE_ENVIRONMENT_ID=abc12345
DYNATRACE_API_KEY=dt0c01.XXXXXXXXXX...
DT_OTLP_ENDPOINT=https://abc12345.live.dynatrace.com/api/v2/otlp
DT_API_TOKEN=dt0c01.XXXXXXXXXX...

# Development
USE_SECRET_MANAGER=false
```

### ✅ Step 3: Test Credentials
```bash
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

print('=== Credential Check ===')
print(f'GCP_PROJECT_ID: {os.getenv(\"GCP_PROJECT_ID\", \"❌ NOT SET\")}')
print(f'GEMINI_API_KEY: {\"✓ SET\" if os.getenv(\"GEMINI_API_KEY\") else \"❌ NOT SET\"}')
print(f'DYNATRACE_API_KEY: {\"✓ SET\" if os.getenv(\"DYNATRACE_API_KEY\") else \"❌ NOT SET\"}')
"
```

### ✅ Step 4: Run Application
```bash
python aire/services/main.py
```

---

## 🚨 SECURITY BEST PRACTICES

⚠️ **NEVER commit `.env` file to version control!**

✅ **DO:**
- Use `.env` for local development only
- Use Google Cloud Secret Manager in production
- Rotate API keys regularly
- Grant minimal required permissions to service accounts
- Use environment variable secrets in CI/CD pipelines

❌ **DON'T:**
- Store secrets in code
- Commit `.env` files
- Share API keys in emails or chat
- Use the same key for development and production
- Log sensitive data

---

## 📞 SUPPORT & DOCUMENTATION

| Service | Docs Link |
|---------|-----------|
| Google Cloud | https://cloud.google.com/docs |
| Gemini API | https://ai.google.dev/docs |
| Dynatrace | https://docs.dynatrace.com/ |
| BindPlane | https://bindplane.bluemedora.com/docs |
| Vertex AI | https://cloud.google.com/vertex-ai/docs |

---

## 🔄 PRODUCTION DEPLOYMENT

For Cloud Run deployment, follow this flow:

1. **Create secrets in Google Cloud Secret Manager:**
   ```bash
   gcloud secrets create aire-dynatrace-api-key --data-file=- <<< "dt0c01.XXXXXXXXXX..."
   gcloud secrets create aire-gemini-api-key --data-file=- <<< "AIzaSyXXXXXXXXXXXXXXX..."
   gcloud secrets create aire-bindplane-api-key --data-file=- <<< "bindplane-key"
   ```

2. **Deploy to Cloud Run:**
   ```bash
   gcloud run deploy aire-backend \
     --source . \
     --set-env-vars USE_SECRET_MANAGER=true,GCP_PROJECT_ID=my-project \
     --secret DYNATRACE_API_KEY=aire-dynatrace-api-key:latest \
     --secret GEMINI_API_KEY=aire-gemini-api-key:latest \
     --secret BINDPLANE_API_KEY=aire-bindplane-api-key:latest
   ```

3. **Verify via logs:**
   ```bash
   gcloud run logs read aire-backend
   ```

---

**Last Updated:** 2026-06-07
**Project:** AIRE (AI Reliability Engine)
