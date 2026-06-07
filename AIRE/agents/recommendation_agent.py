"""
Recommendation Agent — Layer 4.
Synthesizes outputs from Reliability, Root Cause, and Cost agents
into a prioritized set of actionable recommendations.
"""

import json
import logging
from dataclasses import dataclass, asdict

from gemini_client import GeminiClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are AIRE's Recommendation Agent — the final synthesizer in the AI reliability pipeline.

You receive analysis from three specialized agents:
1. Reliability Agent — scored the agent's reliability (0–100)
2. Root Cause Agent — identified why failures are occurring
3. Cost Agent — found optimization opportunities

Your job is to produce the Top 3–5 prioritized recommendations that an engineering
team should act on FIRST, combining insights from all three agents.

Prioritization framework:
- P0: Immediate — production impact, act within 24 hours
- P1: High — significant impact, act within 1 week
- P2: Medium — notable improvement, act within 1 month
- P3: Low — nice to have, act when capacity allows

Always respond with valid JSON only. Be specific: "add retry logic with exponential backoff"
not "improve error handling"."""

REC_SCHEMA = """{
  "executive_summary": <string — 2-3 sentence summary for engineering leadership>,
  "agent_health_overview": {
    "reliability_score": <number>,
    "grade": <string>,
    "primary_issue": <string>,
    "trend": <"IMPROVING"|"STABLE"|"DEGRADING">
  },
  "recommendations": [
    {
      "id": <string — "REC-001" etc.>,
      "priority": <"P0"|"P1"|"P2"|"P3">,
      "title": <string>,
      "what": <string — exactly what to do>,
      "why": <string — business impact if not done>,
      "how": <string — specific implementation steps>,
      "effort_days": <number>,
      "impact": <string — expected outcome after implementation>,
      "sources": [<"reliability"|"root_cause"|"cost">, ...]
    }
  ],
  "do_not_do": [<string — common wrong approaches to avoid>, ...],
  "success_metrics": [
    {"metric": <string>, "current": <string>, "target": <string>, "measure_by": <string>}
  ]
}"""


@dataclass
class Recommendation:
    id: str
    priority: str
    title: str
    what: str
    why: str
    how: str
    effort_days: int
    impact: str
    sources: list[str]


@dataclass
class RecommendationReport:
    agent_name: str
    executive_summary: str
    agent_health_overview: dict
    recommendations: list[Recommendation]
    do_not_do: list[str]
    success_metrics: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def p0_items(self) -> list[Recommendation]:
        return [r for r in self.recommendations if r.priority == "P0"]

    @property
    def quick_wins(self) -> list[Recommendation]:
        return [r for r in self.recommendations if r.effort_days <= 2]


class RecommendationAgent:
    def __init__(self, gemini_client: GeminiClient | None = None):
        self.gemini = gemini_client or GeminiClient(
            model_name="gemini-1.5-pro",
            system_instruction=SYSTEM_PROMPT,
            force_json=True,
        )
        logger.info("RecommendationAgent initialized")

    def synthesize(
        self,
        agent_name: str,
        reliability_result: dict,
        rca_result: dict,
        cost_result: dict,
        rag_context: str = "",
    ) -> RecommendationReport:
        """
        Synthesize all agent outputs into prioritized recommendations.
        """
        logger.info("Synthesizing recommendations for '%s'", agent_name)

        prompt = f"""Synthesize analysis from three specialized agents into actionable recommendations.

Agent Under Analysis: {agent_name}

=== RELIABILITY ANALYSIS RESULTS ===
Score: {reliability_result.get("score", 0)}/100 (Grade: {reliability_result.get("grade", "?")})
Summary: {reliability_result.get("summary", "")}
Critical Issues: {json.dumps(reliability_result.get("critical_issues", []))}
Risk Level: {reliability_result.get("risk_level", "UNKNOWN")}

=== ROOT CAUSE ANALYSIS RESULTS ===
Root Cause: {rca_result.get("root_cause", {}).get("title", "Unknown")}
Category: {rca_result.get("root_cause", {}).get("category", "Unknown")}
Confidence: {rca_result.get("root_cause", {}).get("confidence", 0):.0%}
Description: {rca_result.get("root_cause", {}).get("description", "")}
Blast Radius: {json.dumps(rca_result.get("blast_radius", {}))}

=== COST OPTIMIZATION RESULTS ===
Current Monthly Cost: ${cost_result.get("current_cost_analysis", {}).get("estimated_monthly_usd", 0):.2f}
Projected Savings: ${cost_result.get("total_projected_savings_usd_monthly", 0):.2f}/mo
Top Cost Issues: {json.dumps([o.get("title") for o in cost_result.get("optimizations", [])[:3]])}
"""

        if rag_context:
            prompt += f"\n=== BEST PRACTICES FROM KNOWLEDGE BASE ===\n{rag_context}\n"

        prompt += f"\nSynthesize into Top 3–5 prioritized recommendations. Respond with JSON:\n{REC_SCHEMA}"

        try:
            result = self.gemini.generate_json(prompt)

            recommendations = [
                Recommendation(**{
                    k: v for k, v in rec.items()
                    if k in Recommendation.__dataclass_fields__
                })
                for rec in result.get("recommendations", [])
            ]

            report = RecommendationReport(
                agent_name=agent_name,
                executive_summary=result.get("executive_summary", ""),
                agent_health_overview=result.get("agent_health_overview", {}),
                recommendations=recommendations,
                do_not_do=result.get("do_not_do", []),
                success_metrics=result.get("success_metrics", []),
            )

            p0_count = len(report.p0_items)
            logger.info(
                "Recommendations for '%s': %d total (%d P0)",
                agent_name, len(recommendations), p0_count
            )

            if p0_count > 0:
                logger.warning(
                    "⚠️  %d P0 (IMMEDIATE) recommendations for '%s'",
                    p0_count, agent_name
                )

            return report

        except Exception as e:
            logger.error("Recommendation synthesis failed for '%s': %s", agent_name, e)
            raise