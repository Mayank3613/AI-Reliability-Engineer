# Project Structure

```text
aire/
│
├── apps/                                  # Demo AI Applications
│   ├── customer_support_agent.py
│   ├── research_agent.py
│   ├── coding_agent.py
│   ├── enterprise_agent.py
│   └── otel_setup.py
│
├── observability/                         # Dynatrace Layer
│   ├── dynatrace_client.py
│   ├── otel_exporter.py
│   ├── trace_collector.py
│   ├── metric_collector.py
│   └── dynatrace_config.yaml
│
├── telemetry_pipeline/                    # Bindplane Layer
│   ├── bindplane_config.yaml
│   ├── otel_collector.yaml
│   ├── transform_rules.py
│   └── routing_rules.py
│
├── agent_builder/                         # Gemini Agent Builder
│   ├── workflows/
│   │   ├── reliability_workflow.yaml
│   │   ├── root_cause_workflow.yaml
│   │   ├── recommendation_workflow.yaml
│   │   └── orchestration_workflow.yaml
│   │
│   └── configs/
│       ├── agent_builder_config.yaml
│       └── orchestration_config.yaml
│
├── agents/                                # Gemini Enterprise Agent Platform
│   │
│   ├── reliability_agent.py
│   ├── root_cause_agent.py
│   ├── cost_agent.py
│   ├── recommendation_agent.py
│   ├── agent_orchestrator.py
│   └── gemini_client.py
│
│   └── extensions/                        # Agent Builder Extensions
│       ├── dynatrace_extension.py
│       ├── telemetry_extension.py
│       ├── scoring_extension.py
│       └── recommendation_extension.py
│
├── knowledge/                             # Agent Search + Data Stores
│   ├── datastore_client.py
│   ├── agent_search.py
│   ├── conversation_memory.py
│   ├── document_loader.py
│   ├── rag_pipeline.py
│   └── embeddings.py
│
│   └── docs/                              # Upload to Agent Search
│       ├── reliability_playbooks.md
│       ├── prompt_engineering_guide.md
│       ├── ai_best_practices.md
│       └── internal_sops.md
│
├── services/                              # Cloud Run Services
│   ├── reliability_scorer.py
│   ├── cost_analyzer.py
│   ├── optimization_calc.py
│   ├── recommendation_api.py
│   ├── simulation_service.py
│   └── main.py
│
├── security/                              # Secret Manager Layer
│   ├── secret_manager.py
│   ├── credentials.py
│   └── .env.example
│
├── deploy/                                # Deployment Layer
│   ├── cloudbuild.yaml
│   ├── cloud_run_service.yaml
│   ├── agent_runtime.py
│   ├── deploy.sh
│   └── Dockerfile
│
├── safety/                                # Gemini Safety Controls
│   ├── safety_config.py
│   ├── safety_rules.yaml
│   └── action_validator.py
│
├── dashboard/                             # Frontend UI
│   ├── src/
│   │   ├── components/
│   │   │   ├── ReliabilityScore.jsx
│   │   │   ├── RootCausePanel.jsx
│   │   │   ├── CostInsights.jsx
│   │   │   ├── AgentComparison.jsx
│   │   │   └── Recommendations.jsx
│   │   │
│   │   ├── pages/
│   │   │   └── Dashboard.jsx
│   │   │
│   │   └── App.jsx
│   │
│   └── package.json
│
├── tests/                                 # Unit + Integration Tests
│   ├── test_agents.py
│   ├── test_scoring.py
│   ├── test_pipeline.py
│   └── test_recommendations.py
│
├── scripts/                               # Development Utilities
│   ├── seed_demo_data.py
│   ├── generate_telemetry.py
│   └── reset_env.sh
│
├── README.md
├── architecture.md
├── requirements.txt
├── pyproject.toml
├── docker-compose.yml
└── .env.example
```
# AIRE — AI Agent Reliability Engineer

AIRE monitors, scores, and improves enterprise AI agents using Dynatrace observability data and Gemini-powered reasoning on Google Cloud.

## Architecture

```
AI Applications (OTel instrumented)
         ↓
Dynatrace Observability (traces, metrics, logs)
         ↓
Bindplane Telemetry Pipeline (collect → normalize → route)
         ↓
Gemini Agent Platform (Reliability · Root Cause · Cost · Recommendation)
         ↓
Agent Search / RAG (grounded recommendations)
         ↓
Cloud Run Backend (scoring · cost analysis · optimization simulation)
         ↓
AIRE Dashboard (React · real-time insights)
```

## Quick Start

### Prerequisites
- Google Cloud project with billing enabled
- Dynatrace environment (free trial works)
- `gcloud` CLI authenticated

### Local Development

```bash
# 1. Clone and configure
cp security/.env.example .env
# Fill in GCP_PROJECT_ID, DYNATRACE_* values

# 2. Start all services
docker compose up -d

# 3. Start demo agents (generates telemetry)
docker compose --profile demo up -d

# 4. Open dashboard
open http://localhost:3000

# 5. View API docs
open http://localhost:8080/docs
```

### Deploy to Google Cloud

```bash
export GCP_PROJECT_ID=your-project-id
./deploy/deploy.sh --project $GCP_PROJECT_ID --region us-central1
```

## Project Structure

```
aire/
├── apps/                    # Demo AI agents (generate telemetry)
├── observability/           # Dynatrace + OTel integration
├── telemetry_pipeline/      # Bindplane pipeline config
├── agents/                  # Gemini agent implementations
├── knowledge/               # RAG pipeline + Agent Search
│   └── docs/                # Knowledge base documents
├── services/                # Cloud Run FastAPI backend
├── security/                # Secret Manager integration
├── deploy/                  # Deployment configs (Cloud Run, K8s, CI/CD)
├── safety/                  # Gemini safety settings + action validation
├── dashboard/               # React frontend
├── tests/                   # Unit + integration tests
└── scripts/                 # Dev utilities
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| POST | `/api/v1/reliability/score` | Score a single agent |
| POST | `/api/v1/reliability/score-batch` | Score multiple agents |
| POST | `/api/v1/cost/analyze` | Full cost report + suggestions |
| POST | `/api/v1/optimize/simulate` | Simulate optimization scenarios |

Full API docs: `http://localhost:8080/docs`

## Google Cloud Resources Used

| Layer | Resource |
|-------|----------|
| Observability | Dynatrace Agent Platform + Gemini Enterprise Monitoring |
| Telemetry | Bindplane (Google Edition) |
| Agents | Gemini Enterprise Agent Platform |
| Knowledge | Agent Search + Agent Conversation + Data Store |
| Backend | Cloud Run |
| Security | Secret Manager |
| Deployment | Agent Runtime + Agent Deployment |
| Safety | Gemini Safety Settings |

## Running Tests

```bash
# Unit tests only
pytest tests/ -v --ignore=tests/test_integration.py

# All tests (requires GCP credentials)
pytest tests/ -v
```
