"""
Cost Optimization Agent — Layer 4.
Analyzes token usage, context sizes, and model choices.
Produces concrete cost reduction recommendations with projected savings.
"""

import json
import logging
from dataclasses import dataclass, asdict

from gemini_client import GeminiClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are AIRE's Cost Optimization Agent — an expert in LLM cost efficiency.

You analyze token usage patterns and model configurations to identify waste and
recommend optimizations. You always quantify projected savings with realistic estimates.

Optimization strategies you know:
1. Context window reduction — trim unnecessary preamble/history
2. Model right-sizing — use Flash for simple tasks, Pro for complex ones
3. Prompt compression — remove redundant instructions
4. Retrieval optimization — reduce RAG chunk count
5. Caching — cache common prompts/responses
6. Batching — combine multiple small requests
7. Output length control — set max_tokens to fit task requirements

Always respond with valid JSON only. Be specific with numbers."""

COST_SCHEMA = """{
  "current_cost_analysis": {
    "estimated_hourly_usd": <number>,
    "estimated_monthly_usd": <number>,
    "tokens_per_call_avg": <number>,
    "most_expensive_agent": <string>,
    "cost_per_successful_call_usd": <number>
  },
  "optimizations": [
    {
      "id": <string — unique id e.g. "opt_001">,
      "title": <string>,
      "strategy": <string — one of the 7 strategies above>,
      "description": <string — specific, actionable>,
      "current_tokens": <number>,
      "projected_tokens": <number>,
      "reduction_percent": <number>,
      "estimated_monthly_savings_usd": <number>,
      "implementation_effort": <"LOW"|"MEDIUM"|"HIGH">,
      "risk": <"LOW"|"MEDIUM"|"HIGH">,
      "code_change_required": <boolean>
    }
  ],
  "priority_order": [<optimization id>, ...],
  "total_projected_savings_usd_monthly": <number>,
  "savings_percent": <number>
}"""

# Gemini pricing (per 1M tokens, as of 2024)
PRICING = {
    "gemini-1.5-pro": {"input": 3.50, "output": 10.50},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.0-pro": {"input": 0.50, "output": 1.50},
}


@dataclass
class CostOptimization:
    id: str
    title: str
    strategy: str
    description: str
    current_tokens: int
    projected_tokens: int
    reduction_percent: float
    estimated_monthly_savings_usd: float
    implementation_effort: str
    risk: str
    code_change_required: bool


@dataclass
class CostReport:
    agent_name: str
    current_cost_analysis: dict
    optimizations: list[CostOptimization]
    priority_order: list[str]
    total_projected_savings_usd_monthly: float
    savings_percent: float

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def quick_wins(self) -> list[CostOptimization]:
        """Return LOW effort, LOW risk optimizations first."""
        return [
            o for o in self.optimizations
            if o.implementation_effort == "LOW" and o.risk == "LOW"
        ]


class CostAgent:
    def __init__(self, gemini_client: GeminiClient | None = None):
        self.gemini = gemini_client or GeminiClient(
            model_name="gemini-1.5-flash",  # Use Flash for cost analysis — ironic efficiency
            system_instruction=SYSTEM_PROMPT,
            force_json=True,
        )
        logger.info("CostAgent initialized")

    def _estimate_current_cost(self, metrics: dict) -> dict:
        """Pre-compute cost estimates from raw metrics."""
        model = metrics.get("model", "gemini-1.5-pro")
        pricing = PRICING.get(model, {"input": 1.0, "output": 3.0})

        total_tokens = metrics.get("total_tokens", 0)
        prompt_tokens = total_tokens * 0.7  # estimate 70/30 split
        completion_tokens = total_tokens * 0.3
        calls = max(metrics.get("llm_calls", 1), 1)
        errors = metrics.get("error_count", 0)

        hourly_cost = (
            (prompt_tokens / 1_000_000) * pricing["input"]
            + (completion_tokens / 1_000_000) * pricing["output"]
        )

        return {
            "model": model,
            "total_tokens_1h": total_tokens,
            "estimated_hourly_usd": round(hourly_cost, 4),
            "estimated_monthly_usd": round(hourly_cost * 24 * 30, 2),
            "avg_tokens_per_call": round(total_tokens / calls, 0),
            "error_rate": round(errors / calls, 4),
            "wasted_cost_on_errors_usd": round(
                (errors / calls) * hourly_cost, 4
            ),
        }

    def analyze(
        self,
        agent_name: str,
        metrics: dict,
        token_breakdown: list[dict],
        rag_context: str = "",
    ) -> CostReport:
        """Generate cost optimization recommendations."""
        logger.info("Cost analysis for '%s'", agent_name)

        cost_estimate = self._estimate_current_cost(metrics)

        prompt = f"""Analyze the cost efficiency of this AI agent and recommend optimizations.

Agent: {agent_name}
Model: {metrics.get("model", "gemini-1.5-pro")}
Analysis window: 1 hour (extrapolate to monthly)

=== CURRENT COSTS ===
{json.dumps(cost_estimate, indent=2)}

=== TOKEN USAGE BREAKDOWN (by operation type) ===
{json.dumps(token_breakdown[:20], indent=2)}

=== ADDITIONAL METRICS ===
- P95 latency: {metrics.get("p95_latency_ms", 0):.0f}ms
- RAG chunks per query (avg): {metrics.get("avg_rag_chunks", 0)}
- Context window utilization: {metrics.get("context_utilization", 0):.0%}
"""

        if rag_context:
            prompt += f"\n=== COST OPTIMIZATION BEST PRACTICES ===\n{rag_context}\n"

        prompt += f"\nProvide specific, actionable optimizations. Respond with JSON:\n{COST_SCHEMA}"

        try:
            result = self.gemini.generate_json(prompt)

            optimizations = [
                CostOptimization(**{
                    k: v for k, v in opt.items()
                    if k in CostOptimization.__dataclass_fields__
                })
                for opt in result.get("optimizations", [])
            ]

            report = CostReport(
                agent_name=agent_name,
                current_cost_analysis=result.get("current_cost_analysis", cost_estimate),
                optimizations=optimizations,
                priority_order=result.get("priority_order", []),
                total_projected_savings_usd_monthly=result.get(
                    "total_projected_savings_usd_monthly", 0
                ),
                savings_percent=result.get("savings_percent", 0),
            )

            logger.info(
                "Cost analysis for '%s': $%.2f/mo → save $%.2f/mo (%.0f%%)",
                agent_name,
                report.current_cost_analysis.get("estimated_monthly_usd", 0),
                report.total_projected_savings_usd_monthly,
                report.savings_percent,
            )
            return report

        except Exception as e:
            logger.error("Cost analysis failed for '%s': %s", agent_name, e)
            raise