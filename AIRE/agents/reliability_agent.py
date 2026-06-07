"""
Reliability Analysis Agent — Layer 4.
Uses Gemini to analyze trace + metric data and produce a Reliability Score (0–100)
with a breakdown of contributing factors.
"""

import json
import logging
from dataclasses import dataclass, asdict

from gemini_client import GeminiClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are AIRE's Reliability Analysis Agent — an expert AI systems reliability engineer.

Your job is to analyze telemetry data from AI agents (traces, metrics, errors) and produce
a structured reliability assessment.

You score reliability on a scale of 0–100:
- 90–100: Excellent — production ready
- 70–89:  Good — minor issues, acceptable for production
- 50–69:  Fair — significant issues, needs attention before scale
- 30–49:  Poor — blocking issues, not production ready
- 0–29:   Critical — severe failures, immediate action required

Always respond with valid JSON only. No prose outside the JSON structure."""

SCORING_SCHEMA = """{
  "reliability_score": <number 0-100>,
  "grade": <"A"|"B"|"C"|"D"|"F">,
  "summary": <string, 1-2 sentences>,
  "breakdown": {
    "success_rate": {"score": <0-100>, "weight": 0.35, "detail": <string>},
    "latency": {"score": <0-100>, "weight": 0.25, "detail": <string>},
    "error_patterns": {"score": <0-100>, "weight": 0.20, "detail": <string>},
    "tool_stability": {"score": <0-100>, "weight": 0.20, "detail": <string>}
  },
  "critical_issues": [<string>, ...],
  "positive_signals": [<string>, ...],
  "risk_level": <"LOW"|"MEDIUM"|"HIGH"|"CRITICAL">
}"""


@dataclass
class ReliabilityScore:
    agent_name: str
    score: float
    grade: str
    summary: str
    breakdown: dict
    critical_issues: list[str]
    positive_signals: list[str]
    risk_level: str
    raw_data_summary: dict

    def to_dict(self) -> dict:
        return asdict(self)


class ReliabilityAgent:
    def __init__(self, gemini_client: GeminiClient | None = None):
        self.gemini = gemini_client or GeminiClient(
            model_name="gemini-1.5-pro",
            system_instruction=SYSTEM_PROMPT,
            force_json=True,
        )
        logger.info("ReliabilityAgent initialized")

    def _build_analysis_prompt(
        self,
        agent_name: str,
        traces: list[dict],
        metrics: dict,
        rag_context: str = "",
    ) -> str:
        # Compute basic stats from traces
        total = len(traces)
        errors = sum(1 for t in traces if not t.get("llm.success", True))
        avg_latency = (
            sum(t.get("llm.latency_ms", 0) for t in traces) / total if total else 0
        )
        tool_failures = sum(
            1 for t in traces
            if t.get("event_type") == "tool_call" and not t.get("llm.success", True)
        )

        data_summary = {
            "agent": agent_name,
            "window": "last 1 hour",
            "total_spans": total,
            "error_count": errors,
            "error_rate": round(errors / total, 4) if total else 0,
            "avg_latency_ms": round(avg_latency, 1),
            "p95_latency_ms": metrics.get("p95_latency_ms", 0),
            "total_tokens": metrics.get("total_tokens", 0),
            "tool_failure_count": tool_failures,
            "llm_call_count": metrics.get("llm_calls", 0),
        }

        prompt = f"""Analyze the reliability of this AI agent and score it.

Agent Name: {agent_name}
Telemetry Window: Last 1 hour

=== METRICS SUMMARY ===
{json.dumps(data_summary, indent=2)}

=== ERROR SAMPLES (first 5) ===
{json.dumps([t for t in traces[:5] if not t.get("llm.success", True)], indent=2)}
"""

        if rag_context:
            prompt += f"\n=== RELIABILITY BEST PRACTICES (from Agent Search) ===\n{rag_context}\n"

        prompt += f"\nRespond with JSON matching exactly this schema:\n{SCORING_SCHEMA}"
        return prompt, data_summary

    def analyze(
        self,
        agent_name: str,
        traces: list[dict],
        metrics: dict,
        rag_context: str = "",
    ) -> ReliabilityScore:
        """Run reliability analysis and return a scored result."""
        logger.info("Analyzing reliability for '%s' (%d traces)", agent_name, len(traces))

        prompt, data_summary = self._build_analysis_prompt(
            agent_name, traces, metrics, rag_context
        )

        try:
            result = self.gemini.generate_json(prompt)

            score = ReliabilityScore(
                agent_name=agent_name,
                score=float(result.get("reliability_score", 0)),
                grade=result.get("grade", "F"),
                summary=result.get("summary", ""),
                breakdown=result.get("breakdown", {}),
                critical_issues=result.get("critical_issues", []),
                positive_signals=result.get("positive_signals", []),
                risk_level=result.get("risk_level", "CRITICAL"),
                raw_data_summary=data_summary,
            )

            logger.info(
                "Reliability score for '%s': %.1f (%s) — Risk: %s",
                agent_name, score.score, score.grade, score.risk_level
            )
            return score

        except Exception as e:
            logger.error("Reliability analysis failed for '%s': %s", agent_name, e)
            raise

    def analyze_all(
        self,
        agent_data: list[tuple[str, list[dict], dict]],
        rag_context: str = "",
    ) -> list[ReliabilityScore]:
        """Analyze multiple agents and return all scores."""
        scores = []
        for agent_name, traces, metrics in agent_data:
            try:
                score = self.analyze(agent_name, traces, metrics, rag_context)
                scores.append(score)
            except Exception as e:
                logger.error("Skipping '%s' due to error: %s", agent_name, e)
        return sorted(scores, key=lambda s: s.score)