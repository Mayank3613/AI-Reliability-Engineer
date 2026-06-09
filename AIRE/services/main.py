"""
Layer 6 — Cloud Run Services
main.py: FastAPI application serving all AIRE backend endpoints.
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from AIRE.services.reliability_scorer import (
    AgentMetrics,
    calculate_reliability_score,
    score_multiple_agents,
)
from AIRE.services.cost_analyzer import (
    TokenUsageRecord,
    analyze_agent_costs,
    generate_optimization_suggestions,
    calculate_session_cost,
)
from AIRE.services.optimization_calc import simulate_context_reduction, simulate_model_tiering
from AIRE.services.recommendation_api import (
    build_recommendation,
    bundle_recommendations,
    format_recommendations_for_api,
    Category,
    Priority,
)

app = FastAPI(
    title="AIRE Backend API",
    description="AI Agent Reliability Engineer — Cloud Run Backend",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================================
# Health
# ==================================================================

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/debug-version")
def debug_version():
    return {"version": "2.0.0", "batch_type": "list[MetricsPayload] | AgentBatchPayload"}


# ==================================================================
# Pydantic Models
# ==================================================================

class MetricsPayload(BaseModel):
    """Single-agent metrics payload for /reliability/score."""

    # Agent Identity
    agent_id: str
    name: Optional[str] = None          # friendly display name (optional)
    agent_type: str

    # Request Metrics
    total_requests: int
    successful_requests: int
    failed_requests: int

    # Latency Metrics
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float

    # Tool Usage Metrics
    total_tool_calls: int
    failed_tool_calls: int

    # Token Usage Metrics
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int

    # Hallucination Metrics
    # Accepts both 0–1 fraction and 0–100 percent — normalised automatically
    hallucinated_responses: int = 0
    hallucination_rate: float = 0.0

    # RAG / Grounding Metrics
    grounded_responses: int = 0
    retrieval_success_rate: float = 1.0

    # Error Analytics
    error_types: Dict[str, int] = Field(default_factory=dict)

    # Observation Window
    time_window_minutes: int = 60

    # Cost (informational)
    cost_per_request: float = 0.0

    def to_agent_metrics(self) -> AgentMetrics:
        """Convert to AgentMetrics dataclass, using agent_id as canonical id."""
        data = self.dict(exclude={"name", "cost_per_request"})
        return AgentMetrics(**data)


class AgentEntry(BaseModel):
    """One agent entry from the bulk JSON payload format."""
    agent_id: str
    name: Optional[str] = None
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

    hallucinated_responses: int = 0
    hallucination_rate: float = 0.0     # percent (1–100) or fraction (0–1)

    grounded_responses: int = 0
    retrieval_success_rate: float = 1.0

    error_types: Dict[str, int] = Field(default_factory=dict)
    time_window_minutes: int = 60
    cost_per_request: float = 0.0

    def to_agent_metrics(self) -> AgentMetrics:
        data = self.dict(exclude={"name", "cost_per_request"})
        return AgentMetrics(**data)


class AgentBatchPayload(BaseModel):
    """Bulk payload: { 'agents': [ ... ] }"""
    agents: List[AgentEntry]


class UsageRecordPayload(BaseModel):
    agent_id: str
    agent_type: str
    session_id: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    timestamp: str          # ISO format
    retrieval_chunks: int = 0
    tool_calls: int = 0


class SimulationPayload(BaseModel):
    current_prompt_tokens: int
    current_completion_tokens: int
    current_latency_ms: float
    current_cost_usd: float
    scenario: str = "context_reduction"
    monthly_sessions: int = 10000
    retrieval_chunk_reduction: int = 7


# ==================================================================
# Helper: build the standard score response dict
# ==================================================================

def _score_response(result, metrics: AgentMetrics, name: Optional[str] = None) -> dict:
    base = {
        "agent_id": result.agent_id,
        "agent_type": result.agent_type,
        "overall_score": round(result.overall_score, 2),
        "grade": result.grade,
        "interpretation": result.interpretation,
        "sub_scores": {
            "success_rate":             round(result.success_rate_score, 2),
            "latency":                  round(result.latency_score, 2),
            "tool_stability":           round(result.tool_stability_score, 2),
            "hallucination_resistance": round(result.hallucination_score, 2),
            "retrieval_quality":        round(result.retrieval_score, 2),
            "grounding":                round(result.grounding_score, 2),
            "error_rate":               round(result.error_rate_score, 2),
        },
        "metrics_summary": {
            "total_requests":        metrics.total_requests,
            "success_rate":          round(
                metrics.successful_requests / max(metrics.total_requests, 1), 4
            ),
            "hallucination_rate":    metrics.hallucination_rate,
            "retrieval_success_rate": metrics.retrieval_success_rate,
            "grounded_responses":    metrics.grounded_responses,
            "p95_latency_ms":        metrics.p95_latency_ms,
        },
        "key_issues": result.key_issues,
    }
    if name:
        base["name"] = name
    return base


# ==================================================================
# Reliability Endpoints
# ==================================================================

@app.post("/api/v1/reliability/score")
def score_agent(payload: MetricsPayload):
    """Score a single agent."""
    metrics = payload.to_agent_metrics()
    result = calculate_reliability_score(metrics)
    return _score_response(result, metrics, name=payload.name)


@app.post("/api/v1/reliability/score-batch")
def score_agents_batch(payloads: List[MetricsPayload]):
    """Score a list of agents (array format)."""
    metrics_list = [p.to_agent_metrics() for p in payloads]
    results = score_multiple_agents(metrics_list)

    name_map = {p.agent_id: p.name for p in payloads}
    return [
        _score_response(r, m, name=name_map.get(r.agent_id))
        for r, m in zip(results, sorted(metrics_list, key=lambda m: m.agent_id))
    ]


@app.post("/api/v1/reliability/analyze-batch")
def analyze_batch(payload: AgentBatchPayload):
    """
    Accept the { 'agents': [...] } JSON structure and return full
    reliability scores + cost estimates + recommendations for every agent.

    Example input:
    {
      "agents": [
        {
          "agent_id": "agent_001",
          "name": "Customer Support Agent",
          "agent_type": "chatbot",
          "total_requests": 1000,
          ...
          "hallucination_rate": 1,      <- percent or fraction, both accepted
          "cost_per_request": 0.01
        },
        ...
      ]
    }
    """
    if not payload.agents:
        raise HTTPException(status_code=400, detail="agents list is empty")

    results = []
    for entry in payload.agents:
        metrics = entry.to_agent_metrics()
        score = calculate_reliability_score(metrics)

        # ── Cost estimation ───────────────────────────────────────
        # Derive a synthetic cost from cost_per_request or token counts
        cost_per_session = entry.cost_per_request or calculate_session_cost(
            entry.prompt_tokens,
            entry.completion_tokens,
        )
        estimated_monthly_cost = cost_per_session * entry.total_requests

        # ── Recommendations ───────────────────────────────────────
        recs = []
        rec_counter = 0

        if score.success_rate_score < 80:
            rec_counter += 1
            recs.append(build_recommendation(
                rec_id=f"{entry.agent_id}-rec-{rec_counter:03d}",
                agent_id=entry.agent_id,
                agent_type=entry.agent_type,
                category=Category.RELIABILITY,
                priority=Priority.CRITICAL,
                title="Improve Success Rate",
                problem=f"Success rate is {metrics.successful_requests / max(metrics.total_requests, 1):.1%}, well below the 95% target.",
                solution="Audit the most frequent failure paths. Add retry logic with exponential back-off for transient errors.",
                expected_impact="Could recover 10–15 reliability points.",
                steps=[
                    "Classify all failed_requests by error type",
                    "Add retry with jitter for 5xx / timeout errors",
                    "Alert on success_rate dropping below 90%",
                ],
                effort="2 hours",
                impact_score=9.0,
                source_agent="reliability_scorer",
            ))

        if score.hallucination_score < 80:
            rec_counter += 1
            recs.append(build_recommendation(
                rec_id=f"{entry.agent_id}-rec-{rec_counter:03d}",
                agent_id=entry.agent_id,
                agent_type=entry.agent_type,
                category=Category.QUALITY,
                priority=Priority.HIGH,
                title="Reduce Hallucination Rate",
                problem=f"Hallucination rate is {metrics.hallucination_rate:.1%} (target < 3%).",
                solution="Enable Grounding with Google Search / Vertex AI Search. Add a post-generation factuality checker.",
                expected_impact="Reduce hallucination rate by 50–70%.",
                steps=[
                    "Enable `google_search_retrieval` tool in the agent config",
                    "Add a confidence-score threshold; re-generate if score < 0.6",
                    "Log hallucinated responses for fine-tuning feedback loop",
                ],
                effort="1 day",
                impact_score=8.5,
                source_agent="reliability_scorer",
            ))

        if score.latency_score < 70:
            rec_counter += 1
            recs.append(build_recommendation(
                rec_id=f"{entry.agent_id}-rec-{rec_counter:03d}",
                agent_id=entry.agent_id,
                agent_type=entry.agent_type,
                category=Category.LATENCY,
                priority=Priority.HIGH,
                title="Reduce P99 Latency",
                problem=f"P99 latency is {metrics.p99_latency_ms:.0f} ms (target ≤ 2000 ms).",
                solution="Reduce retrieval context size, enable prompt caching, and consider model tiering for simple queries.",
                expected_impact="30–50% latency reduction.",
                steps=[
                    "Enable Gemini implicit prompt caching for static system prompt",
                    "Reduce top_k RAG chunks from current to ≤ 5",
                    "Route simple requests to gemini-2.0-flash",
                ],
                effort="2 hours",
                impact_score=7.5,
                source_agent="reliability_scorer",
            ))

        if score.tool_stability_score < 75:
            rec_counter += 1
            recs.append(build_recommendation(
                rec_id=f"{entry.agent_id}-rec-{rec_counter:03d}",
                agent_id=entry.agent_id,
                agent_type=entry.agent_type,
                category=Category.RELIABILITY,
                priority=Priority.HIGH,
                title="Fix Tool Call Failures",
                problem=f"Tool call failure rate is {metrics.failed_tool_calls / max(metrics.total_tool_calls, 1):.1%}.",
                solution="Add timeouts, circuit breakers, and structured retry logic around external tool calls.",
                expected_impact="Reduce tool failures by 60–80%.",
                steps=[
                    "Wrap each tool call in a try/except with structured error logging",
                    "Set explicit timeout (≤ 10 s) on all external API calls",
                    "Implement exponential back-off for retriable errors",
                ],
                effort="3 hours",
                impact_score=7.0,
                source_agent="reliability_scorer",
            ))

        bundle = bundle_recommendations(
            agent_id=entry.agent_id,
            agent_type=entry.agent_type,
            reliability_score=score.overall_score,
            all_recommendations=recs,
            cost_savings_usd=estimated_monthly_cost * (score.overall_score / 100) * 0.2,
        )

        results.append({
            **_score_response(score, metrics, name=entry.name),
            "cost_estimate": {
                "cost_per_request_usd": round(cost_per_session, 6),
                "estimated_monthly_cost_usd": round(estimated_monthly_cost, 2),
            },
            "recommendations": format_recommendations_for_api(bundle)["recommendations"],
        })

    # ── Summary ───────────────────────────────────────────────────
    avg_score = sum(r["overall_score"] for r in results) / len(results)
    total_monthly = sum(r["cost_estimate"]["estimated_monthly_cost_usd"] for r in results)

    return {
        "summary": {
            "total_agents": len(results),
            "average_reliability_score": round(avg_score, 2),
            "estimated_total_monthly_cost_usd": round(total_monthly, 2),
            "agents_needing_attention": sum(1 for r in results if r["overall_score"] < 80),
        },
        "agents": results,
    }


# ==================================================================
# Cost Endpoints
# ==================================================================

@app.post("/api/v1/cost/analyze")
def analyze_cost(records_payload: List[UsageRecordPayload], period_days: int = 7):
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


# ==================================================================
# Optimization Simulation
# ==================================================================

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


# ==================================================================
# Dashboard Data  (legacy / Dynatrace-based endpoint)
# ==================================================================

@app.get("/api/v1/dashboard/data")
def get_dashboard_data():
    """
    Legacy dashboard endpoint that attempts to pull from Dynatrace and
    falls back to simulated data.  The new primary path is
    POST /api/v1/reliability/analyze-batch.
    """
    try:
        from agents.agent_orchestrator import AgentOrchestrator
        from observability.dynatrace_client import DynatraceClient
        from observability.trace_collector import TraceCollector
        from observability.metric_collector import MetricCollector
    except ImportError:
        # Observability stack not available in this deployment
        return _simulated_dashboard()

    traces = []
    metrics_snapshots = []

    try:
        dt_client = DynatraceClient()
        trace_collector = TraceCollector(dt_client)
        metric_collector = MetricCollector(dt_client)

        services = [
            "customer-support-agent",
            "research-agent",
            "coding-agent",
            "enterprise-agent",
        ]
        traces = trace_collector.collect(services, hours=1)
        metrics_snapshots = metric_collector.build_snapshots(hours=1)
    except Exception as e:
        print(f"[AIRE Backend] Dynatrace skipped: {e}")

    return _build_dashboard_response(traces, metrics_snapshots)


def _simulated_dashboard() -> dict:
    """Return a fully-simulated dashboard payload (no Dynatrace required)."""
    agents = [
        AgentEntry(
            agent_id="customer-support-agent",
            name="Customer Support Agent",
            agent_type="chatbot",
            total_requests=100,
            successful_requests=92,
            failed_requests=8,
            p50_latency_ms=1100,
            p95_latency_ms=1850,
            p99_latency_ms=30000,
            total_tool_calls=80,
            failed_tool_calls=8,
            total_tokens=284000,
            prompt_tokens=198800,
            completion_tokens=85200,
            hallucination_rate=0.02,
        ),
        AgentEntry(
            agent_id="research-agent",
            name="Research Agent",
            agent_type="rag",
            total_requests=50,
            successful_requests=43,
            failed_requests=7,
            p50_latency_ms=1800,
            p95_latency_ms=3100,
            p99_latency_ms=4200,
            total_tool_calls=70,
            failed_tool_calls=7,
            total_tokens=428000,
            prompt_tokens=299600,
            completion_tokens=128400,
            hallucination_rate=0.05,
            retrieval_success_rate=0.86,
        ),
        AgentEntry(
            agent_id="coding-agent",
            name="Coding Agent",
            agent_type="code",
            total_requests=50,
            successful_requests=49,
            failed_requests=1,
            p50_latency_ms=900,
            p95_latency_ms=1100,
            p99_latency_ms=1800,
            total_tool_calls=60,
            failed_tool_calls=1,
            total_tokens=680000,
            prompt_tokens=476000,
            completion_tokens=204000,
            hallucination_rate=0.01,
        ),
        AgentEntry(
            agent_id="enterprise-agent",
            name="Enterprise Agent",
            agent_type="enterprise",
            total_requests=50,
            successful_requests=47,
            failed_requests=3,
            p50_latency_ms=1500,
            p95_latency_ms=2200,
            p99_latency_ms=5000,
            total_tool_calls=55,
            failed_tool_calls=3,
            total_tokens=340000,
            prompt_tokens=238000,
            completion_tokens=102000,
            hallucination_rate=0.03,
        ),
    ]
    batch_result = analyze_batch(AgentBatchPayload(agents=agents))
    return _format_dashboard(batch_result)


def _build_dashboard_response(traces, metrics_snapshots) -> dict:
    """Build dashboard from Dynatrace data (stub — extend as needed)."""
    return _simulated_dashboard()


def _format_dashboard(batch_result: dict) -> dict:
    agents_data = batch_result["agents"]
    summary = batch_result["summary"]

    overview_cards = [
        {"label": "Active agents",       "value": str(summary["total_agents"]),                          "detail": "Telemetry live"},
        {"label": "Average reliability", "value": f"{summary['average_reliability_score']:.0f}%",        "detail": "Stable" if summary["average_reliability_score"] >= 80 else "Action required"},
        {"label": "Cost forecast",       "value": f"${summary['estimated_total_monthly_cost_usd']:,.2f}", "detail": "Projected monthly spend"},
        {"label": "Open incidents",      "value": str(summary["agents_needing_attention"]),               "detail": f"{summary['agents_needing_attention']} needing attention"},
    ]

    agents_list = [
        {
            "name":   a.get("name", a["agent_id"]),
            "score":  a["overall_score"],
            "health": (
                "Excellent" if a["overall_score"] >= 90 else
                "Good"      if a["overall_score"] >= 80 else
                "Fair"      if a["overall_score"] >= 70 else
                "Poor"      if a["overall_score"] >= 55 else
                "Critical"
            ),
            "spend": f"${a['cost_estimate']['estimated_monthly_cost_usd']:,.2f}",
        }
        for a in agents_data
    ]

    primary = min(agents_data, key=lambda a: a["overall_score"])

    total_spend = summary["estimated_total_monthly_cost_usd"]
    total_savings = sum(
        sum(r.get("impact_score", 0) * 0.5 for r in a.get("recommendations", []))
        for a in agents_data
    )
    opt_val = max(0.0, total_spend - total_savings)

    cost_metrics = [
        {"label": "Current spend",        "value": f"${total_spend:,.2f}",   "progress": 100,                                                                 "color": "#5ba4f7"},
        {"label": "Model optimization",   "value": f"${opt_val:,.2f}",       "progress": int((opt_val / total_spend) * 100) if total_spend else 100,          "color": "#36d6b3"},
        {"label": "Potential savings",    "value": f"${total_savings:,.2f}", "progress": int((total_savings / total_spend) * 100) if total_spend else 0,      "color": "#ffb020"},
    ]

    causes_list = [
        {"title": issue, "detail": issue, "severity": "HIGH" if "Critical" in primary["grade"] else "MEDIUM"}
        for issue in primary.get("key_issues", [])
        if issue != "No significant issues detected"
    ] or [{"title": "All systems operating normally", "detail": "No active incidents detected.", "severity": "Low"}]

    recs_list = []
    for a in agents_data:
        for r in a.get("recommendations", [])[:2]:
            recs_list.append({"title": f"[{a.get('name', a['agent_id'])}] {r['title']}", "tag": r["priority"].upper()})

    return {
        "overviewCards": overview_cards,
        "agents": agents_list,
        "reliability": {
            "score":   primary["overall_score"],
            "grade":   primary["grade"],
            "trend":   "+6%",
            "risk":    "HIGH" if primary["overall_score"] < 70 else "MEDIUM" if primary["overall_score"] < 85 else "LOW",
            "summary": primary["interpretation"],
        },
        "causes": causes_list,
        "costMetrics": cost_metrics,
        "recommendations": recs_list[:4],
    }


# ==================================================================
# Entry point
# ==================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
