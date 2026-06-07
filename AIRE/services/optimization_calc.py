"""
Layer 6 — Cloud Run Services
Optimization Calculator: Simulates before/after impacts of optimizations.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class OptimizationScenario:
    name: str
    description: str
    changes: dict  # {parameter: (current_value, proposed_value)}


@dataclass
class OptimizationResult:
    scenario_name: str
    current_tokens_per_session: float
    projected_tokens_per_session: float
    token_reduction_pct: float
    current_latency_ms: float
    projected_latency_ms: float
    latency_reduction_pct: float
    current_cost_per_session_usd: float
    projected_cost_per_session_usd: float
    cost_savings_per_session_usd: float
    monthly_sessions_estimate: int
    monthly_savings_usd: float
    annual_savings_usd: float
    reliability_score_impact: float
    implementation_effort: str
    risks: list[str]
    recommendations: list[str]


def simulate_context_reduction(
    current_prompt_tokens: int,
    current_completion_tokens: int,
    current_latency_ms: float,
    current_cost_usd: float,
    retrieval_chunk_reduction: int = 7,  # reduce by N chunks
    tokens_per_chunk: int = 400,
    monthly_sessions: int = 10000,
) -> OptimizationResult:
    """
    Simulate the effect of reducing retrieval context chunks.
    """
    tokens_saved = retrieval_chunk_reduction * tokens_per_chunk
    projected_prompt = max(500, current_prompt_tokens - tokens_saved)

    # Latency scales roughly linearly with prompt token count for prefill
    latency_reduction_factor = tokens_saved / max(current_prompt_tokens, 1) * 0.6
    projected_latency = current_latency_ms * (1 - latency_reduction_factor)

    # Cost scales with tokens
    projected_cost = current_cost_usd * (projected_prompt / max(current_prompt_tokens, 1))

    token_reduction_pct = (tokens_saved / max(current_prompt_tokens, 1)) * 100
    latency_reduction_pct = latency_reduction_factor * 100
    cost_savings = current_cost_usd - projected_cost
    monthly_savings = cost_savings * monthly_sessions
    annual_savings = monthly_savings * 12

    return OptimizationResult(
        scenario_name="Context Reduction",
        current_tokens_per_session=current_prompt_tokens + current_completion_tokens,
        projected_tokens_per_session=projected_prompt + current_completion_tokens,
        token_reduction_pct=round(token_reduction_pct, 1),
        current_latency_ms=current_latency_ms,
        projected_latency_ms=round(projected_latency, 1),
        latency_reduction_pct=round(latency_reduction_pct, 1),
        current_cost_per_session_usd=current_cost_usd,
        projected_cost_per_session_usd=round(projected_cost, 6),
        cost_savings_per_session_usd=round(cost_savings, 6),
        monthly_sessions_estimate=monthly_sessions,
        monthly_savings_usd=round(monthly_savings, 2),
        annual_savings_usd=round(annual_savings, 2),
        reliability_score_impact=+2.5,  # Less timeout risk with smaller context
        implementation_effort="Low — adjust top_k in RAG pipeline config",
        risks=[
            "Reduced context may lower answer quality for complex multi-source queries",
            "Ensure re-ranker selects high-quality chunks from smaller set",
        ],
        recommendations=[
            f"Reduce retrieval chunks by {retrieval_chunk_reduction} (apply MMR re-ranking)",
            "Run A/B test: 20% traffic with reduced context, monitor quality metrics",
            "Set quality floor: discard chunks with relevance_score < 0.45",
        ],
    )


def simulate_model_tiering(
    current_model: str,
    current_cost_per_session_usd: float,
    current_latency_ms: float,
    pct_simple_tasks: float = 0.60,
    monthly_sessions: int = 10000,
) -> OptimizationResult:
    """
    Simulate routing simple tasks to Gemini Flash instead of Pro.
    """
    # Flash is ~16x cheaper than Pro for input, ~16x for output
    flash_cost_ratio = 0.06  # Flash ≈ 6% of Pro cost
    projected_cost = current_cost_per_session_usd * (
        (1 - pct_simple_tasks) + pct_simple_tasks * flash_cost_ratio
    )

    # Flash is ~2x faster than Pro
    projected_latency = current_latency_ms * (
        (1 - pct_simple_tasks) + pct_simple_tasks * 0.5
    )

    cost_savings = current_cost_per_session_usd - projected_cost
    token_reduction_pct = pct_simple_tasks * 30  # approximate

    return OptimizationResult(
        scenario_name="Model Tiering (Pro → Flash for simple tasks)",
        current_tokens_per_session=0,  # N/A for this scenario
        projected_tokens_per_session=0,
        token_reduction_pct=round(token_reduction_pct, 1),
        current_latency_ms=current_latency_ms,
        projected_latency_ms=round(projected_latency, 1),
        latency_reduction_pct=round((1 - projected_latency / current_latency_ms) * 100, 1),
        current_cost_per_session_usd=current_cost_per_session_usd,
        projected_cost_per_session_usd=round(projected_cost, 6),
        cost_savings_per_session_usd=round(cost_savings, 6),
        monthly_sessions_estimate=monthly_sessions,
        monthly_savings_usd=round(cost_savings * monthly_sessions, 2),
        annual_savings_usd=round(cost_savings * monthly_sessions * 12, 2),
        reliability_score_impact=-1.0,  # slight quality risk
        implementation_effort="Medium — requires task complexity classifier",
        risks=[
            "Flash may produce lower-quality answers for complex reasoning tasks",
            "Need a reliable complexity classifier to route correctly",
            f"Current model '{current_model}' may have tuned outputs — Flash behavior differs",
        ],
        recommendations=[
            "Build task complexity scorer: route score < 0.6 to Flash",
            "Start with 10% traffic, measure quality via human eval or LLM-as-judge",
            f"Estimated to save ${cost_savings * monthly_sessions:.2f}/month at {monthly_sessions} sessions/month",
        ],
    )


def simulate_prompt_caching(
    current_prompt_tokens: int,
    current_cost_usd: float,
    static_system_prompt_pct: float = 0.40,
    monthly_sessions: int = 10000,
) -> OptimizationResult:
    """
    Simulate using Gemini prompt caching for static system prompt portions.
    """
    # Cached tokens cost ~4x less than regular input tokens
    cache_savings_factor = 0.75  # 75% savings on cached portion
    cached_tokens = int(current_prompt_tokens * static_system_prompt_pct)
    savings_per_session = current_cost_usd * static_system_prompt_pct * cache_savings_factor
    projected_cost = current_cost_usd - savings_per_session

    return OptimizationResult(
        scenario_name="Prompt Caching (static system prompt)",
        current_tokens_per_session=current_prompt_tokens,
        projected_tokens_per_session=current_prompt_tokens,  # tokens same, cost changes
        token_reduction_pct=0.0,  # tokens don't reduce, just cost
        current_latency_ms=0,  # N/A
        projected_latency_ms=0,
        latency_reduction_pct=0.0,
        current_cost_per_session_usd=current_cost_usd,
        projected_cost_per_session_usd=round(projected_cost, 6),
        cost_savings_per_session_usd=round(savings_per_session, 6),
        monthly_sessions_estimate=monthly_sessions,
        monthly_savings_usd=round(savings_per_session * monthly_sessions, 2),
        annual_savings_usd=round(savings_per_session * monthly_sessions * 12, 2),
        reliability_score_impact=+1.0,
        implementation_effort="Low — structure system prompt for caching",
        risks=[
            "Cache TTL means stale system prompt if updated frequently",
            "Not beneficial for highly dynamic prompts",
        ],
        recommendations=[
            f"Separate {static_system_prompt_pct:.0%} static instructions into cacheable prefix",
            "Use Gemini implicit caching — no code changes needed for prefix > 1024 tokens",
            f"Estimated to save ${savings_per_session * monthly_sessions:.2f}/month",
        ],
    )
