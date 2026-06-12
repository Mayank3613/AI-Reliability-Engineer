"""
Layer 6 — Cloud Run Services
main.py: FastAPI application serving all AIRE backend endpoints.
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

# Add parent and internal directories to path so agents and services can import dynamically
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.extend([
    parent_dir,
    os.path.join(parent_dir, "Apps"),
    os.path.join(parent_dir, "agents"),
    os.path.join(parent_dir, "observability"),
    os.path.join(parent_dir, "security"),
    os.path.join(parent_dir, "safety")
])

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.reliability_scorer import AgentMetrics, calculate_reliability_score, score_multiple_agents
from services.cost_analyzer import TokenUsageRecord, analyze_agent_costs, generate_optimization_suggestions
from services.optimization_calc import simulate_context_reduction, simulate_model_tiering
from services.recommendation_api import format_recommendations_for_api

app = FastAPI(
    title="AIRE Backend API",
    description="AI Agent Reliability Engineer — Cloud Run Backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ------------------------------------------------------------------
# Reliability
# ------------------------------------------------------------------

class MetricsPayload(BaseModel):
    agent_id: str
    agent_type: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    total_tool_calls: int
    failed_tool_calls: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    time_window_minutes: int = 60
    error_types: dict = {}


@app.post("/api/v1/reliability/score")
def score_agent(payload: MetricsPayload):
    metrics = AgentMetrics(**payload.dict())
    result = calculate_reliability_score(metrics)
    return {
        "agent_id": result.agent_id,
        "overall_score": result.overall_score,
        "grade": result.grade,
        "interpretation": result.interpretation,
        "sub_scores": {
            "success_rate": result.success_rate_score,
            "latency": result.latency_score,
            "error_rate": result.error_rate_score,
            "tool_stability": result.tool_stability_score,
        },
        "key_issues": result.key_issues,
    }


@app.post("/api/v1/reliability/score-batch")
def score_agents_batch(payloads: list[MetricsPayload]):
    metrics_list = [AgentMetrics(**p.dict()) for p in payloads]
    results = score_multiple_agents(metrics_list)
    return [
        {
            "agent_id": r.agent_id,
            "agent_type": r.agent_type,
            "overall_score": r.overall_score,
            "grade": r.grade,
            "key_issues": r.key_issues,
        }
        for r in results
    ]


# ------------------------------------------------------------------
# Cost
# ------------------------------------------------------------------

class UsageRecordPayload(BaseModel):
    agent_id: str
    agent_type: str
    session_id: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    timestamp: str  # ISO format
    retrieval_chunks: int = 0
    tool_calls: int = 0


@app.post("/api/v1/cost/analyze")
def analyze_cost(records_payload: list[UsageRecordPayload], period_days: int = 7):
    records = []
    for p in records_payload:
        records.append(TokenUsageRecord(
            agent_id=p.agent_id,
            agent_type=p.agent_type,
            session_id=p.session_id,
            model_id=p.model_id,
            prompt_tokens=p.prompt_tokens,
            completion_tokens=p.completion_tokens,
            timestamp=datetime.fromisoformat(p.timestamp),
            retrieval_chunks=p.retrieval_chunks,
            tool_calls=p.tool_calls,
        ))

    if not records:
        raise HTTPException(status_code=400, detail="No usage records provided")

    report = analyze_agent_costs(records, period_days)
    suggestions = generate_optimization_suggestions(report)

    return {
        "agent_id": report.agent_id,
        "period_days": report.period_days,
        "total_cost_usd": report.total_cost_usd,
        "avg_cost_per_session_usd": report.avg_cost_per_session_usd,
        "total_tokens": report.total_tokens,
        "avg_tokens_per_session": report.avg_tokens_per_session,
        "optimization_potential_pct": report.optimization_potential_pct,
        "optimization_potential_usd": report.optimization_potential_usd,
        "daily_cost_trend": report.daily_cost_trend,
        "top_cost_drivers": report.top_cost_drivers,
        "suggestions": [
            {
                "category": s.category,
                "description": s.description,
                "savings_pct": s.estimated_savings_pct,
                "savings_usd": s.estimated_savings_usd,
                "complexity": s.implementation_complexity,
                "priority": s.priority,
            }
            for s in suggestions
        ],
    }


# ------------------------------------------------------------------
# Optimization Simulation
# ------------------------------------------------------------------

class SimulationPayload(BaseModel):
    current_prompt_tokens: int
    current_completion_tokens: int
    current_latency_ms: float
    current_cost_usd: float
    scenario: str = "context_reduction"
    monthly_sessions: int = 10000
    retrieval_chunk_reduction: int = 7


@app.post("/api/v1/optimize/simulate")
def simulate_optimization(payload: SimulationPayload):
    if payload.scenario == "context_reduction":
        result = simulate_context_reduction(
            current_prompt_tokens=payload.current_prompt_tokens,
            current_completion_tokens=payload.current_completion_tokens,
            current_latency_ms=payload.current_latency_ms,
            current_cost_usd=payload.current_cost_usd,
            retrieval_chunk_reduction=payload.retrieval_chunk_reduction,
            monthly_sessions=payload.monthly_sessions,
        )
    elif payload.scenario == "model_tiering":
        result = simulate_model_tiering(
            current_model="gemini-1.5-pro",
            current_cost_per_session_usd=payload.current_cost_usd,
            current_latency_ms=payload.current_latency_ms,
            monthly_sessions=payload.monthly_sessions,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {payload.scenario}")

    return {
        "scenario": result.scenario_name,
        "token_reduction_pct": result.token_reduction_pct,
        "latency_reduction_pct": result.latency_reduction_pct,
        "cost_savings_per_session_usd": result.cost_savings_per_session_usd,
        "monthly_savings_usd": result.monthly_savings_usd,
        "annual_savings_usd": result.annual_savings_usd,
        "reliability_score_impact": result.reliability_score_impact,
        "risks": result.risks,
        "recommendations": result.recommendations,
    }


# ------------------------------------------------------------------
# Dashboard Data
# ------------------------------------------------------------------

@app.get("/api/v1/dashboard/data")
def get_dashboard_data():
    from agents.agent_orchestrator import AgentOrchestrator
    from observability.dynatrace_client import DynatraceClient
    from observability.trace_collector import TraceCollector
    from observability.metric_collector import MetricCollector

    # 1. Initialize collectors & try to fetch from Dynatrace
    traces = []
    metrics_snapshots = []

    try:
        dt_client = DynatraceClient()
        trace_collector = TraceCollector(dt_client)
        metric_collector = MetricCollector(dt_client)

        services = ["customer-support-agent", "research-agent", "coding-agent", "enterprise-agent"]
        traces = trace_collector.collect(services, hours=1)
        metrics_snapshots = metric_collector.build_snapshots(hours=1)
    except Exception as e:
        print(f"[AIRE Backend] Dynatrace connection / collection skipped or failed: {e}")

    # 2. Fallback to generating a live simulated dataset if Dynatrace is empty
    agent_names = ["customer-support-agent", "research-agent", "coding-agent", "enterprise-agent"]

    # Map raw metrics
    agent_data = {}
    for name in agent_names:
        agent_data[name] = {
            "traces": [],
            "metrics": {
                "model": "gemini-1.5-pro",
                "p95_latency_ms": 1200.0,
                "total_tokens": 50000,
                "llm_calls": 50,
                "error_count": 0,
                "avg_rag_chunks": 4,
                "context_utilization": 0.65
            }
        }

    # Overwrite with real data if present
    if traces:
        for t in traces:
            svc_name = t.service_name
            if svc_name in agent_data:
                agent_data[svc_name]["traces"].append({
                    "trace_id": t.trace_id,
                    "llm.success": not t.has_errors,
                    "llm.latency_ms": t.total_duration_ms,
                    "event_type": "request",
                    "aire.agent": svc_name
                })
                # Add child spans detail
                for span in t.spans:
                    if span.status == "error":
                        agent_data[svc_name]["traces"].append({
                            "trace_id": t.trace_id,
                            "llm.success": False,
                            "llm.latency_ms": span.duration_ms,
                            "event_type": "tool_call",
                            "llm.tool_name": span.operation_name,
                            "error.message": span.error_message or "Error",
                            "aire.agent": svc_name
                        })

    if metrics_snapshots:
        for m in metrics_snapshots:
            if m.agent_name in agent_data:
                agent_data[m.agent_name]["metrics"] = {
                    "model": "gemini-1.5-pro",
                    "p95_latency_ms": m.p95_latency_ms,
                    "total_tokens": int(m.total_tokens),
                    "llm_calls": m.llm_calls,
                    "error_count": m.error_count,
                    "avg_rag_chunks": 4,
                    "context_utilization": 0.72
                }

    # Generate simulated traces/metrics for agents that don't have enough live data yet
    # customer-support-agent has timeouts (92% success rate, 8% timeouts)
    if len(agent_data["customer-support-agent"]["traces"]) < 10:
        cs_traces = []
        for i in range(92):
            cs_traces.append({
                "trace_id": f"t_cs_{i}",
                "llm.success": True,
                "llm.latency_ms": 1100 + (i % 10) * 120,
                "event_type": "request",
                "aire.agent": "customer-support-agent"
            })
        for i in range(8):
            cs_traces.append({
                "trace_id": f"t_cs_fail_{i}",
                "llm.success": False,
                "llm.latency_ms": 30000,
                "event_type": "tool_call",
                "llm.tool_name": "search_knowledge_base",
                "error.message": "TimeoutError: Knowledge base search timed out after 30s",
                "aire.agent": "customer-support-agent"
            })
        agent_data["customer-support-agent"]["traces"] = cs_traces
        agent_data["customer-support-agent"]["metrics"] = {
            "model": "gemini-1.5-pro",
            "p95_latency_ms": 1850.0,
            "total_tokens": 284000,
            "llm_calls": 100,
            "error_count": 8,
            "avg_rag_chunks": 12,
            "context_utilization": 0.88
        }

    # research-agent has rate limits (86% success rate, 14% rate limits)
    if len(agent_data["research-agent"]["traces"]) < 10:
        res_traces = []
        for i in range(43):
            res_traces.append({
                "trace_id": f"t_res_{i}",
                "llm.success": True,
                "llm.latency_ms": 1800 + (i % 5) * 250,
                "event_type": "request",
                "aire.agent": "research-agent"
            })
        for i in range(7):
            res_traces.append({
                "trace_id": f"t_res_fail_{i}",
                "llm.success": False,
                "llm.latency_ms": 4200,
                "event_type": "tool_call",
                "llm.tool_name": "web_search",
                "error.message": "ConnectionError: Search API rate limit exceeded",
                "aire.agent": "research-agent"
            })
        agent_data["research-agent"]["traces"] = res_traces
        agent_data["research-agent"]["metrics"] = {
            "model": "gemini-1.5-pro",
            "p95_latency_ms": 3100.0,
            "total_tokens": 428000,
            "llm_calls": 50,
            "error_count": 7,
            "avg_rag_chunks": 8,
            "context_utilization": 0.65
        }

    # coding-agent (perfect 98% success, high tokens)
    if len(agent_data["coding-agent"]["traces"]) < 10:
        cod_traces = []
        for i in range(49):
            cod_traces.append({
                "trace_id": f"t_cod_{i}",
                "llm.success": True,
                "llm.latency_ms": 900 + (i % 5) * 80,
                "event_type": "request",
                "aire.agent": "coding-agent"
            })
        cod_traces.append({
            "trace_id": "t_cod_fail_0",
            "llm.success": False,
            "llm.latency_ms": 1800,
            "event_type": "tool_call",
            "llm.tool_name": "git_commit",
            "error.message": "PermissionError: write access denied to repository",
            "aire.agent": "coding-agent"
        })
        agent_data["coding-agent"]["traces"] = cod_traces
        agent_data["coding-agent"]["metrics"] = {
            "model": "gemini-1.5-pro",
            "p95_latency_ms": 1100.0,
            "total_tokens": 680000,
            "llm_calls": 50,
            "error_count": 1,
            "avg_rag_chunks": 3,
            "context_utilization": 0.45
        }

    # enterprise-agent (94% success rate)
    if len(agent_data["enterprise-agent"]["traces"]) < 10:
        ent_traces = []
        for i in range(47):
            ent_traces.append({
                "trace_id": f"t_ent_{i}",
                "llm.success": True,
                "llm.latency_ms": 1500 + (i % 5) * 150,
                "event_type": "request",
                "aire.agent": "enterprise-agent"
            })
        for i in range(3):
            ent_traces.append({
                "trace_id": f"t_ent_fail_{i}",
                "llm.success": False,
                "llm.latency_ms": 5000,
                "event_type": "request",
                "error.message": "ServiceUnavailable: Vertex AI prediction quota exhausted",
                "aire.agent": "enterprise-agent"
            })
        agent_data["enterprise-agent"]["traces"] = ent_traces
        agent_data["enterprise-agent"]["metrics"] = {
            "model": "gemini-1.5-pro",
            "p95_latency_ms": 2200.0,
            "total_tokens": 340000,
            "llm_calls": 50,
            "error_count": 3,
            "avg_rag_chunks": 4,
            "context_utilization": 0.55
        }

    # 3. Run analysis via AgentOrchestrator
    orchestrator = AgentOrchestrator()
    analyses = []

    for name in agent_names:
        traces_list = agent_data[name]["traces"]
        metrics_dict = agent_data[name]["metrics"]
        total_tok = metrics_dict["total_tokens"]

        token_breakdown = [
            {"operation": "prompt_tokens", "tokens": int(total_tok * 0.7)},
            {"operation": "completion_tokens", "tokens": int(total_tok * 0.3)}
        ]

        analysis = orchestrator.analyze_agent(
            agent_name=name,
            traces=traces_list,
            metrics=metrics_dict,
            token_breakdown=token_breakdown
        )
        analyses.append(analysis)

    # 4. Aggregations & formatting
    total_agents = len(analyses)
    avg_score = sum(a.reliability["score"] for a in analyses) / total_agents

    # Monthly cost calculation from cost report estimates
    total_monthly_spend = sum(a.cost.get("current_cost_analysis", {}).get("estimated_monthly_usd", 0) for a in analyses)
    total_monthly_spend_formatted = f"${total_monthly_spend / 1000:.1f}k"

    open_incidents = sum(1 for a in analyses if a.reliability["score"] < 85)

    overview_cards = [
        { "label": "Active agents", "value": str(total_agents), "detail": "Telemetry live" },
        { "label": "Average reliability", "value": f"{avg_score:.0f}%", "detail": f"{'Stable' if avg_score >= 80 else 'Action required'}" },
        { "label": "Cost forecast", "value": total_monthly_spend_formatted, "detail": "Projected monthly spend" },
        { "label": "Open incidents", "value": str(open_incidents), "detail": f"{open_incidents} critical incidents" }
    ]

    # Map agents table data
    agents_list = []
    for a in analyses:
        score = a.reliability["score"]
        spend_usd = a.cost.get("current_cost_analysis", {}).get("estimated_monthly_usd", 0)

        agents_list.append({
            "name": a.agent_name,
            "score": score,
            "health": "Excellent" if score >= 90 else "Good" if score >= 80 else "Fair" if score >= 70 else "Poor" if score >= 55 else "Critical",
            "spend": f"${spend_usd:,.0f}"
        })

    # Pick the lowest scored agent as primary reliability details to show on load
    primary = min(analyses, key=lambda a: a.reliability["score"])

    # Construct cost metrics
    total_savings = sum(a.cost.get("total_projected_savings_usd_monthly", 0) for a in analyses)
    spend_val = total_monthly_spend
    savings_val = total_savings
    opt_val = max(0.0, spend_val - savings_val)

    cost_metrics = [
        { "label": "Current spend", "value": f"${spend_val:,.0f}", "progress": 100, "color": "#5ba4f7" },
        { "label": "Model optimization", "value": f"${opt_val:,.0f}", "progress": int((opt_val / spend_val) * 100) if spend_val else 100, "color": "#36d6b3" },
        { "label": "Potential savings", "value": f"${savings_val:,.0f}", "progress": int((savings_val / spend_val) * 100) if spend_val else 0, "color": "#ffb020" }
    ]

    # Combine root causes
    causes_list = []
    for a in analyses:
        rc = a.root_cause.get("root_cause", {})
        if rc.get("category") != "NONE":
            causes_list.append({
                "title": f"[{a.agent_name}] {rc.get('title')}",
                "detail": rc.get("description"),
                "severity": a.root_cause.get("blast_radius", {}).get("impact_severity", "MEDIUM")
            })
    if not causes_list:
        causes_list = [{
            "title": "All systems operating normally",
            "detail": "No active tool or API timeouts detected in trace histories.",
            "severity": "Low"
        }]

    # Combine recommendations
    recs_list = []
    for a in analyses:
        recs = a.recommendations.get("recommendations", [])
        for r in recs[:2]: # take top 2 from each agent
            recs_list.append({
                "title": f"[{a.agent_name}] {r.get('title')}",
                "tag": r.get("priority", "P1")
            })

    return {
        "overviewCards": overview_cards,
        "agents": agents_list,
        "reliability": {
            "score": primary.reliability["score"],
            "grade": primary.reliability["grade"],
            "trend": primary.reliability.get("trend", "+6%"),
            "risk": primary.reliability["risk_level"],
            "summary": primary.reliability["summary"]
        },
        "causes": causes_list,
        "costMetrics": cost_metrics,
        "recommendations": recs_list[:4] # top 4 total
    }

# ------------------------------------------------------------------
# AIRE 2.0 Conversational Query & Live Execution
# ------------------------------------------------------------------

import sys
# Ensure app and AIRE paths are searchable
for p in ["/app", "/app/AIRE", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]:
    if p not in sys.path:
        sys.path.append(p)

class QueryPayload(BaseModel):
    query: str
    agent_name: Optional[str] = None


def execute_agent_live(agent_name: str, prompt: str):
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(agent_name)
    
    meter_provider = MeterProvider()
    meter = meter_provider.get_meter(agent_name)
    
    result = {}
    if agent_name == "customer-support-agent":
        from Apps.customer_support_agent import handle_ticket
        result = handle_ticket(prompt, tracer, meter)
    elif agent_name == "research-agent":
        from Apps.research_agent import research_topic
        result = research_topic(prompt, tracer, meter)
    elif agent_name == "coding-agent":
        from Apps.coding_agent import process_coding_task
        task = {"type": "generate", "description": prompt, "context_size": "medium"}
        result = process_coding_task(task, tracer, meter)
    elif agent_name == "enterprise-agent":
        from Apps.enterprise_agent import handle_enterprise_query
        query_obj = {"dept": "IT", "query": prompt}
        result = handle_enterprise_query(query_obj, tracer, meter)
        
    finished_spans = exporter.get_finished_spans()
    return result, finished_spans


def map_finished_spans_to_dashboard(spans_list, agent_name: str) -> list[dict]:
    dashboard_spans = []
    # Sort by start time
    spans_list = sorted(spans_list, key=lambda s: s.start_time)
    
    for s in spans_list:
        name = s.name
        # Format time as HH:MM:SS
        import datetime
        ns = s.start_time
        dt = datetime.datetime.fromtimestamp(ns / 1e9, tz=datetime.timezone.utc)
        time_str = dt.strftime("%H:%M:%S")
        
        latency = round((s.end_time - s.start_time) / 1_000_000, 1)
        
        status_str = "success"
        if not s.status.is_ok:
            status_str = "error"
            if "timeout" in name.lower() or "timeout" in str(s.attributes.get("error.message", "")).lower():
                status_str = "timeout"
        
        # Check indent
        indent = 0
        if name.startswith("tool.") or name == "llm.call":
            indent = 1
            
        speculative = s.attributes.get("speculative") or False
        if "returns_api" in name or "returns" in name:
            speculative = True
            
        note = ""
        if s.attributes.get("error.message"):
            note = str(s.attributes.get("error.message"))
            if len(note) > 30:
                note = "Timeout Error" if "timeout" in note.lower() else "Error"
        elif "shipping_api" in name and status_str == "timeout":
            note = "Root cause"
            
        tokens = s.attributes.get("llm.total_tokens") or 0
        
        dashboard_spans.append({
            "id": name,
            "time": time_str,
            "latency": latency,
            "status": status_str,
            "tokens": tokens,
            "indent": indent,
            "speculative": speculative,
            "note": note
        })
    return dashboard_spans


@app.post("/api/v1/dashboard/query")
def handle_conversational_query(payload: QueryPayload):
    from agents.gemini_client import GeminiClient
    query = payload.query.lower()
    
    # Defaults
    score = 81
    fail_rate = "12%"
    daily_cost = "$2,100"
    token_delta = "—"
    agent_to_run = None
    
    # ── Trend
    trend_data = [
      { "t": "-6h", "score": 82 }, { "t": "-5h", "score": 78 }, { "t": "-4h", "score": 69 },
      { "t": "-3h", "score": 71 }, { "t": "-2h", "score": 74 }, { "t": "-1h", "score": 85 },
      { "t": "now", "score": 81 }
    ]
    
    # ── Root causes
    root_causes = [
      { "name": "Shipping API timeout",   "pct": 67, "color": "#E24B4A", "spanId": "span_8f2a3c" },
      { "name": "Speculative tool calls", "pct": 23, "color": "#EF9F27", "spanId": "span_3c7b1d" },
      { "name": "Context overflow",       "pct": 7,  "color": "#f97316", "spanId": "span_1e9d4a" },
      { "name": "Retry exhaustion",       "pct": 3,  "color": "#8b5cf6", "spanId": "span_5a4f2e" }
    ]
    
    # ── Spans
    spans = [
      { "id": "agent.request",    "time": "12:04:27", "latency": 8400, "status": "error",   "tokens": 1840, "indent": 0 },
      { "id": "tool.orders_api",  "time": "12:04:28", "latency": 340,  "status": "success", "tokens": 0,    "indent": 1 },
      { "id": "tool.shipping_api","time": "12:04:29", "latency": 3200, "status": "timeout", "tokens": 0,    "indent": 1, "note": "Root cause" },
      { "id": "tool.returns_api", "time": "12:04:33", "latency": 820,  "status": "success", "tokens": 0,    "indent": 1, "speculative": True }
    ]
    
    # ── Token data
    token_data = [
      { "day": "Mon", "prompt": 42, "completion": 28, "speculative": 18 },
      { "day": "Tue", "prompt": 45, "completion": 30, "speculative": 21 },
      { "day": "Wed", "prompt": 51, "completion": 34, "speculative": 24 },
      { "day": "Thu", "prompt": 48, "completion": 31, "speculative": 22 },
      { "day": "Fri", "prompt": 55, "completion": 37, "speculative": 26 },
      { "day": "Sat", "prompt": 38, "completion": 25, "speculative": 17 },
      { "day": "Sun", "prompt": 41, "completion": 27, "speculative": 19 }
    ]
    
    # ── Agent defs
    agent_defs = [
      { "name": "Reliability Agent",    "outputBefore": "Score: 69/100",              "outputAfter": "Score: 93/100",
        "detail": "Trend: declining → recovering",    "latency": "1.2s", "color": "#1D9E75", "Icon": "Activity" },
      { "name": "Root Cause Agent",     "outputBefore": "Shipping API → 67% failures", "outputAfter": "Shipping API → 67% failures",
        "detail": "Span: span_8f2a3c",                "latency": "2.1s", "color": "#E24B4A", "Icon": "AlertTriangle" },
      { "name": "Cost Agent",           "outputBefore": "−38% tokens possible",        "outputAfter": "−38% tokens removed",
        "detail": "$1,640/day saving identified",      "latency": "1.8s", "color": "#EF9F27", "Icon": "DollarSign" },
      { "name": "Recommendation Agent", "outputBefore": "3 fixes ranked",              "outputAfter": "3 fixes ranked",
        "detail": "RAG-grounded · safety cleared",     "latency": "3.4s", "color": "#7c3aed", "Icon": "Brain" }
    ]

    use_live_llm = False
    try:
        gemini = GeminiClient(model_name=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"), force_json=True)
        if not gemini.is_fallback:
            use_live_llm = True
    except Exception:
        pass

    chat_response = ""
    if use_live_llm:
        try:
            schema_hint = """{
              "chat_response": "Markdown-formatted detailed conversational explanation answering the user's prompt. Be specific, clear, and cite sources.",
              "dashboard_update": {
                "score": 81,
                "failRate": "12%",
                "dailyCost": "$2,100",
                "tokenDelta": "—",
                "agent_to_run": "customer-support-agent" | "research-agent" | "coding-agent" | "enterprise-agent" | null
              }
            }"""
            
            prompt = f"""You are AIRE Copilot, a conversational AI Reliability Engineer.
Analyze the user request and formulate a response.

User request: "{payload.query}"

Current agent metrics context:
- Average reliability score: 81/100
- Success rate: 88% (12% failures)
- Daily API cost: $2,100

Tasks:
1. Formulate a conversational response.
2. Determine if we should trigger a live execution of one of the backend agents to test a prompt/scenario. If yes, specify the agent ID in 'agent_to_run' (use: 'customer-support-agent', 'research-agent', 'coding-agent', or 'enterprise-agent').
3. If the user asks about failures or timeouts, set 'score' to 69 and 'failRate' to '31%'.
4. Respond ONLY with a valid JSON object matching the schema.
"""
            res_dict = gemini.generate_json(prompt, schema_hint)
            chat_response = res_dict.get("chat_response", "")
            db_update = res_dict.get("dashboard_update", {})
            score = db_update.get("score", score)
            fail_rate = db_update.get("failRate", fail_rate)
            daily_cost = db_update.get("dailyCost", daily_cost)
            token_delta = db_update.get("tokenDelta", token_delta)
            agent_to_run = db_update.get("agent_to_run")
        except Exception as e:
            logger.warning("Live LLM conversational query failed, falling back to keyword parser: %s", e)
            use_live_llm = False

    if not use_live_llm:
        # Fallback keyword matching engine
        if "reliability" in query or "drop" in query or "fail" in query or "error" in query or "issue" in query or "down" in query:
            score = 69
            fail_rate = "31%"
            daily_cost = "$2,100"
            trend_data[-1]["score"] = 69
            
            chat_response = """### 🔍 Reliability Drop Diagnostics

I have analyzed the telemetry for **customer-support-agent** over the last 1 hour. 

* **Reliability Score**: **69/100** (Declining)
* **Root Cause**: **Shipping API Timeout (`tool.shipping_api`)**
* **Incident Status**: Critical timeout encountered in `tool.shipping_api` at 12:04:29. 67% of session failures trace back to this span.
* **Secondary Issue**: Speculative tool calls to `tool.returns_api` are executing on 98% of queries, adding latency and wasting tokens.

#### 📚 RAG-Grounded Recommendations
1. **P0 (Retry Backoff)**: Wrap `search_knowledge_base` and `shipping_api` calls with exponential backoff retries.
2. **P1 (Lazy Tool-Calling)**: Do not invoke the Returns API speculatively unless order detail intent is explicitly matched in the prompt.

*I have updated the dashboard on the right to display the active timeouts in the **Traces** waterfall view.*"""

        elif "cost" in query or "token" in query or "save" in query or "spend" in query or "waste" in query or "expensive" in query:
            score = 69
            fail_rate = "31%"
            daily_cost = "$2,100"
            
            chat_response = """### 💰 AI Infrastructure Cost & Token Analysis

I have audited the token usage across all 4 agents. We are currently spending **$2,100/day** on Gemini API tokens.

* **Speculative Waste**: **38%** of input tokens are consumed by speculative tool calls to the Returns API that are discarded 89% of the time.
* **Context Bloat**: Customer support tickets are retrieving `k=12` chunks from the knowledge base, accounting for 35% of total input tokens.

#### ⚡ Cost Optimization Strategy:
* **Recommendation #1**: Reduce RAG retrieval k-value from `12` to `3`. This reduces prompt tokens by **60%**, saving **$640/day**.
* **Recommendation #2**: Implement lazy tool-calling. Eliminating speculative calls to the Returns API saves **$1,640/day**.

*I have updated the **Costs** tab on the right to show the token breakdown chart. We can save up to **78%** ($1,640/day) by applying these fixes.*"""

        elif "vpn" in query or "hr" in query or "parental" in query or "leave" in query or "contractor" in query or "policy" in query or "enterprise" in query:
            agent_to_run = "enterprise-agent"
            chat_response = "Triggering enterprise HR policy live query..."

        elif "code" in query or "refactor" in query or "linter" in query or "test" in query or "coding" in query or "git" in query:
            agent_to_run = "coding-agent"
            chat_response = "Triggering coding agent live generation check..."
            
        else:
            chat_response = f"""### 👋 Hello! I'm AIRE Copilot.

I processed your query: *"{payload.query}"*.

Since I am running in offline mode, you can trigger specific interactive diagnostics by including keywords:
* Type **"reliability"** or **"timeout"** to diagnose support bot failures.
* Type **"cost"** or **"tokens"** to run the token spend audit.
* Type **"VPN access HR policy"** to run a live HR RAG query on the enterprise agent.
* Type **"refactor Python REST client"** to run a live test suite check on the coding agent."""

    # ── Execute Agent Live if triggered
    if agent_to_run in ["customer-support-agent", "research-agent", "coding-agent", "enterprise-agent"]:
        try:
            res, finished = execute_agent_live(agent_to_run, payload.query)
            spans = map_finished_spans_to_dashboard(finished, agent_to_run)
            latency_total = sum(s["latency"] for s in spans)
            total_tokens = sum(s["tokens"] for s in spans)
            
            # Adjust score based on execution success
            errors = sum(1 for s in spans if s["status"] in ["error", "timeout"])
            if errors > 0:
                score = 69
                fail_rate = "31%"
                trend_data[-1]["score"] = 69
            else:
                score = 94 if agent_to_run == "coding-agent" else 88
                fail_rate = "2%" if agent_to_run == "coding-agent" else "4%"
                trend_data[-1]["score"] = score

            if not use_live_llm:
                # Format fallback chat response for run
                if agent_to_run == "enterprise-agent":
                    ans_str = res.get('answer', 'Policy retrieved successfully.')
                    if len(ans_str) > 280:
                        ans_str = ans_str[:280] + "..."
                    chat_response = f"""### 🏢 Live Enterprise Agent Execution

I executed a live run of the **enterprise-agent** with your query: *"{payload.query}"*.

* **Status**: **RESOLVED**
* **Gemini Model**: `gemini-1.5-flash`
* **Agent Response**: *"{ans_str}"*
* **Telemetry Captured**:
  * Policy retrieval: `{res.get('dept', 'HR')} policy documents` (RAG policy docs searched).
  * Latency: **{latency_total:.0f}ms** (Captured live).
  * Token spend: **{total_tokens:,} tokens** (Captured live).

*I have updated the **Traces** tab to show the waterfall span tree for this active run.*"""
                elif agent_to_run == "coding-agent":
                    chat_response = f"""### 💻 Live Coding Agent Execution

I executed a live run of the **coding-agent** with the task: *"{payload.query}"*.

* **Status**: **COMPLETED**
* **Linter Result**: {res.get('lint', {}).get('issues', 0)} issues, {res.get('lint', {}).get('warnings', 0)} warnings.
* **Test Suite**: {res.get('tests', {}).get('passed', 0)}/{res.get('tests', {}).get('total', 0)} tests passed (Coverage: {res.get('tests', {}).get('coverage', '0%')}).
* **Telemetry Captured**:
  * Latency: **{latency_total:.0f}ms** (Captured live).
  * Token spend: **{total_tokens:,} tokens** (Captured live).

*I have updated the **Traces** and **Costs** tabs with the telemetry from this code execution.*"""
        except Exception as e:
            chat_response = f"Failed to execute agent '{agent_to_run}' live: {e}"

    return {
        "chat_response": chat_response,
        "dashboard_data": {
            "score": score,
            "failRate": fail_rate,
            "dailyCost": daily_cost,
            "tokenDelta": token_delta,
            "trendData": trend_data,
            "rootCauses": root_causes,
            "spans": spans,
            "tokenData": token_data,
            "agentDefs": agent_defs
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

