"""
Layer 6 — Cloud Run Services
main.py: FastAPI application serving all AIRE backend endpoints.
"""

import os
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
