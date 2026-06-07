"""
Layer 6 — Cloud Run Services
Cost Analyzer: Computes per-agent token costs, trends, and savings projections.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta

# Gemini pricing (USD per 1M tokens) — update as needed
GEMINI_PRICING = {
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "default": {"input": 0.075, "output": 0.30},
}


@dataclass
class TokenUsageRecord:
    """A single session's token usage record."""
    agent_id: str
    agent_type: str
    session_id: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    timestamp: datetime
    retrieval_chunks: int = 0
    tool_calls: int = 0


@dataclass
class AgentCostReport:
    """Cost analysis report for a single agent over a period."""
    agent_id: str
    agent_type: str
    model_id: str
    period_days: int
    total_sessions: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: float
    avg_cost_per_session_usd: float
    avg_tokens_per_session: float
    avg_prompt_tokens_per_session: float
    avg_completion_tokens_per_session: float
    daily_cost_trend: list[dict]
    top_cost_drivers: list[str]
    optimization_potential_usd: float
    optimization_potential_pct: float


@dataclass
class CostOptimizationSuggestion:
    category: str
    description: str
    estimated_savings_pct: float
    estimated_savings_usd: float
    implementation_complexity: str  # low / medium / high
    priority: str  # critical / high / medium / low


def _get_model_pricing(model_id: str) -> dict:
    for key in GEMINI_PRICING:
        if key in model_id:
            return GEMINI_PRICING[key]
    return GEMINI_PRICING["default"]


def calculate_session_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model_id: str = "gemini-2.0-flash",
) -> float:
    """Compute USD cost for a single session."""
    pricing = _get_model_pricing(model_id)
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)


def analyze_agent_costs(
    records: list[TokenUsageRecord],
    period_days: int = 7,
) -> AgentCostReport:
    """
    Generate a full cost report for an agent given a list of usage records.
    """
    if not records:
        raise ValueError("No records provided for cost analysis.")

    agent_id = records[0].agent_id
    agent_type = records[0].agent_type
    model_id = records[0].model_id

    total_prompt = sum(r.prompt_tokens for r in records)
    total_completion = sum(r.completion_tokens for r in records)
    total_tokens = total_prompt + total_completion
    total_sessions = len(records)

    pricing = _get_model_pricing(model_id)
    total_cost = calculate_session_cost(total_prompt, total_completion, model_id)

    avg_cost = total_cost / max(total_sessions, 1)
    avg_tokens = total_tokens / max(total_sessions, 1)
    avg_prompt = total_prompt / max(total_sessions, 1)
    avg_completion = total_completion / max(total_sessions, 1)

    # Daily aggregation
    daily_buckets: dict[str, dict] = {}
    for r in records:
        day_key = r.timestamp.strftime("%Y-%m-%d")
        if day_key not in daily_buckets:
            daily_buckets[day_key] = {"prompt": 0, "completion": 0, "sessions": 0}
        daily_buckets[day_key]["prompt"] += r.prompt_tokens
        daily_buckets[day_key]["completion"] += r.completion_tokens
        daily_buckets[day_key]["sessions"] += 1

    daily_trend = []
    for day, data in sorted(daily_buckets.items()):
        day_cost = calculate_session_cost(data["prompt"], data["completion"], model_id)
        daily_trend.append({"date": day, "cost_usd": day_cost, "sessions": data["sessions"]})

    # Cost drivers
    drivers = []
    prompt_pct = total_prompt / max(total_tokens, 1)
    if prompt_pct > 0.75:
        drivers.append(f"Prompt tokens dominate ({prompt_pct:.0%} of total) — likely large system prompts or retrieval chunks")
    avg_retrieval = sum(r.retrieval_chunks for r in records) / max(total_sessions, 1)
    if avg_retrieval > 8:
        drivers.append(f"High retrieval chunk count: avg {avg_retrieval:.1f} chunks/session")
    avg_tool = sum(r.tool_calls for r in records) / max(total_sessions, 1)
    if avg_tool > 5:
        drivers.append(f"High tool call frequency: avg {avg_tool:.1f} calls/session")

    # Optimization potential: estimate 30–40% savings from common fixes
    opt_pct = 0.0
    if avg_prompt > 4000:
        opt_pct += 0.20
    if avg_retrieval > 8:
        opt_pct += 0.15
    if avg_tool > 5:
        opt_pct += 0.05
    opt_usd = round(total_cost * opt_pct, 4)

    return AgentCostReport(
        agent_id=agent_id,
        agent_type=agent_type,
        model_id=model_id,
        period_days=period_days,
        total_sessions=total_sessions,
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost, 4),
        avg_cost_per_session_usd=round(avg_cost, 6),
        avg_tokens_per_session=round(avg_tokens, 1),
        avg_prompt_tokens_per_session=round(avg_prompt, 1),
        avg_completion_tokens_per_session=round(avg_completion, 1),
        daily_cost_trend=daily_trend,
        top_cost_drivers=drivers or ["No dominant cost drivers identified"],
        optimization_potential_usd=opt_usd,
        optimization_potential_pct=round(opt_pct * 100, 1),
    )


def generate_optimization_suggestions(report: AgentCostReport) -> list[CostOptimizationSuggestion]:
    """Generate prioritized cost optimization suggestions from a cost report."""
    suggestions = []

    if report.avg_prompt_tokens_per_session > 4000:
        savings = report.total_cost_usd * 0.20
        suggestions.append(CostOptimizationSuggestion(
            category="Prompt Compression",
            description=f"Average prompt is {report.avg_prompt_tokens_per_session:.0f} tokens. "
                        "Compress system prompt, use prompt caching for static sections.",
            estimated_savings_pct=20.0,
            estimated_savings_usd=round(savings, 4),
            implementation_complexity="low",
            priority="high",
        ))

    avg_retrieval_chunks = sum(1 for d in report.top_cost_drivers if "chunk" in d)
    if avg_retrieval_chunks > 0 or report.avg_prompt_tokens_per_session > 3000:
        savings = report.total_cost_usd * 0.15
        suggestions.append(CostOptimizationSuggestion(
            category="Retrieval Optimization",
            description="Reduce retrieved chunks from current count to top-5 with re-ranking. "
                        "Apply MMR diversity filter to eliminate redundant chunks.",
            estimated_savings_pct=15.0,
            estimated_savings_usd=round(savings, 4),
            implementation_complexity="medium",
            priority="high",
        ))

    if "gemini-1.5-pro" in report.model_id or "gemini-2.5-pro" in report.model_id:
        savings = report.total_cost_usd * 0.60
        suggestions.append(CostOptimizationSuggestion(
            category="Model Tiering",
            description=f"Route simple tasks to Gemini Flash instead of {report.model_id}. "
                        "Use Pro only for complex reasoning steps.",
            estimated_savings_pct=60.0,
            estimated_savings_usd=round(savings, 4),
            implementation_complexity="medium",
            priority="critical",
        ))

    savings = report.total_cost_usd * 0.10
    suggestions.append(CostOptimizationSuggestion(
        category="Response Caching",
        description="Cache identical or near-identical queries. Semantic deduplication "
                    "can eliminate 10–20% of redundant LLM calls.",
        estimated_savings_pct=10.0,
        estimated_savings_usd=round(savings, 4),
        implementation_complexity="high",
        priority="medium",
    ))

    suggestions.sort(key=lambda s: s.estimated_savings_usd, reverse=True)
    return suggestions
