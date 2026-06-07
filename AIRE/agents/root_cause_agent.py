"""
Root Cause Agent — Layer 4.
Uses Gemini to analyze error patterns and traces to identify
the root cause of failures in AI agent systems.
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from collections import Counter

from gemini_client import GeminiClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are AIRE's Root Cause Analysis Agent — an expert in diagnosing
failures in distributed AI agent systems.

Given error traces and telemetry data, you:
1. Identify the root cause (not just symptoms)
2. Trace the failure propagation path
3. Quantify the blast radius
4. Provide a confidence score for your diagnosis

Common failure categories in AI agent systems:
- RATE_LIMIT: API rate limiting from LLM providers or downstream services
- TIMEOUT: Network or computation timeouts
- TOOL_FAILURE: External tool/API failures (search, DB, etc.)
- CONTEXT_OVERFLOW: Prompt too large for model context window
- HALLUCINATION_CASCADE: One bad output triggers downstream failures
- MEMORY_PRESSURE: Container OOM or resource exhaustion
- DEPENDENCY_FAILURE: Third-party service outage

Always respond with valid JSON only."""

RCA_SCHEMA = """{
  "root_cause": {
    "category": <string — one of the failure categories above>,
    "title": <string — short title>,
    "description": <string — detailed explanation>,
    "confidence": <number 0.0–1.0>,
    "evidence": [<string — specific evidence from traces>, ...]
  },
  "failure_chain": [
    {"step": 1, "component": <string>, "event": <string>, "timestamp_relative_ms": <number>},
    ...
  ],
  "blast_radius": {
    "affected_agents": [<string>, ...],
    "affected_spans": <number>,
    "estimated_user_impact": <string>,
    "impact_severity": <"LOW"|"MEDIUM"|"HIGH"|"CRITICAL">
  },
  "contributing_factors": [<string>, ...],
  "false_positives_ruled_out": [<string>, ...]
}"""


@dataclass
class RootCause:
    category: str
    title: str
    description: str
    confidence: float
    evidence: list[str]


@dataclass
class RCAReport:
    agent_name: str
    root_cause: RootCause
    failure_chain: list[dict]
    blast_radius: dict
    contributing_factors: list[str]
    false_positives_ruled_out: list[str]
    error_sample_count: int

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


class RootCauseAgent:
    def __init__(self, gemini_client: GeminiClient | None = None):
        self.gemini = gemini_client or GeminiClient(
            model_name="gemini-1.5-pro",
            system_instruction=SYSTEM_PROMPT,
            force_json=True,
        )
        logger.info("RootCauseAgent initialized")

    def _cluster_errors(self, error_traces: list[dict]) -> dict:
        """Group errors by type before sending to Gemini."""
        error_types = Counter()
        error_messages = []

        for trace in error_traces:
            msg = trace.get("error.message", "")
            event_type = trace.get("event_type", "unknown")
            tool = trace.get("llm.tool_name", "")

            # Classify
            if "timeout" in msg.lower() or "timed out" in msg.lower():
                error_types["TIMEOUT"] += 1
            elif "rate limit" in msg.lower() or "quota" in msg.lower() or "429" in msg:
                error_types["RATE_LIMIT"] += 1
            elif event_type == "tool_call":
                error_types["TOOL_FAILURE"] += 1
            elif "oom" in msg.lower() or "memory" in msg.lower():
                error_types["MEMORY_PRESSURE"] += 1
            elif "context" in msg.lower() or "token" in msg.lower():
                error_types["CONTEXT_OVERFLOW"] += 1
            else:
                error_types["UNKNOWN"] += 1

            if msg and len(error_messages) < 10:
                error_messages.append({
                    "event_type": event_type,
                    "error_message": msg[:200],
                    "tool": tool or None,
                    "latency_ms": trace.get("llm.latency_ms", 0),
                    "agent": trace.get("aire.agent", "unknown"),
                })

        return {
            "error_distribution": dict(error_types),
            "error_samples": error_messages,
            "dominant_error": error_types.most_common(1)[0][0] if error_types else "UNKNOWN",
        }

    def _build_rca_prompt(
        self,
        agent_name: str,
        error_traces: list[dict],
        all_traces: list[dict],
        rag_context: str = "",
    ) -> str:
        clustering = self._cluster_errors(error_traces)
        total = len(all_traces)
        error_rate = round(len(error_traces) / total, 4) if total else 0

        prompt = f"""Perform root cause analysis for failures in this AI agent system.

Agent: {agent_name}
Total spans analyzed: {total}
Error count: {len(error_traces)}
Error rate: {error_rate:.1%}

=== ERROR CLUSTERING ===
{json.dumps(clustering, indent=2)}

=== TIMELINE (recent errors, chronological) ===
{json.dumps(sorted(error_traces[:15], key=lambda x: x.get("timestamp_ms", 0)), indent=2)}
"""

        if rag_context:
            prompt += f"\n=== RELIABILITY PLAYBOOKS (from Agent Search) ===\n{rag_context}\n"

        prompt += f"\nIdentify the ROOT CAUSE, not just symptoms. Respond with JSON:\n{RCA_SCHEMA}"
        return prompt

    def analyze(
        self,
        agent_name: str,
        error_traces: list[dict],
        all_traces: list[dict],
        rag_context: str = "",
    ) -> RCAReport:
        """Perform root cause analysis for an agent's failures."""
        if not error_traces:
            logger.info("No errors found for '%s' — skipping RCA", agent_name)
            return RCAReport(
                agent_name=agent_name,
                root_cause=RootCause(
                    category="NONE",
                    title="No failures detected",
                    description="Agent is operating within normal parameters.",
                    confidence=1.0,
                    evidence=[],
                ),
                failure_chain=[],
                blast_radius={"impact_severity": "LOW"},
                contributing_factors=[],
                false_positives_ruled_out=[],
                error_sample_count=0,
            )

        logger.info(
            "Running RCA for '%s': %d errors / %d total",
            agent_name, len(error_traces), len(all_traces)
        )

        prompt = self._build_rca_prompt(agent_name, error_traces, all_traces, rag_context)

        try:
            result = self.gemini.generate_json(prompt)
            rc_data = result.get("root_cause", {})

            report = RCAReport(
                agent_name=agent_name,
                root_cause=RootCause(
                    category=rc_data.get("category", "UNKNOWN"),
                    title=rc_data.get("title", "Unknown failure"),
                    description=rc_data.get("description", ""),
                    confidence=float(rc_data.get("confidence", 0)),
                    evidence=rc_data.get("evidence", []),
                ),
                failure_chain=result.get("failure_chain", []),
                blast_radius=result.get("blast_radius", {}),
                contributing_factors=result.get("contributing_factors", []),
                false_positives_ruled_out=result.get("false_positives_ruled_out", []),
                error_sample_count=len(error_traces),
            )

            logger.info(
                "RCA for '%s': %s (confidence: %.0f%%)",
                agent_name, report.root_cause.title, report.root_cause.confidence * 100
            )
            return report

        except Exception as e:
            logger.error("RCA failed for '%s': %s", agent_name, e)
            raise