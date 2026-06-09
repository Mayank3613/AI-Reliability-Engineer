"""
Layer 6 — Cloud Run Services
Reliability Scorer: Computes an 0–100 reliability score from telemetry.

Score Formula:
  reliability_score = (
      0.30 * success_rate_score
    + 0.20 * latency_score
    + 0.20 * error_rate_score
    + 0.10 * tool_stability_score
    + 0.10 * hallucination_score
    + 0.05 * retrieval_score
    + 0.05 * grounding_score
  ) * 100
"""

from dataclasses import dataclass, field
from typing import Optional
import math


@dataclass
class AgentMetrics:
    """Raw telemetry metrics for a single agent over a time window."""
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
    error_types: dict = field(default_factory=dict)

    # Hallucination / quality metrics
    # Accepts both fractional (0.0–1.0) and percentage (0–100) form;
    # values > 1.0 are treated as percentage and normalised to fraction.
    hallucinated_responses: int = 0
    hallucination_rate: float = 0.0        # fraction 0.0–1.0  (or % if > 1)

    # RAG / Grounding Metrics
    grounded_responses: int = 0
    retrieval_success_rate: float = 1.0    # fraction 0.0–1.0

    # Optional per-request cost (informational, not used in scoring)
    cost_per_request: float = 0.0

    def __post_init__(self):
        """
        Normalise hallucination_rate to a 0.0–1.0 fraction.

        Accepted input formats:
          • Fraction:  0.01  (already correct — 1%)
          • Percent:   1     (integer percent  — 1%)
          • Percent:   5.0   (float percent    — 5%)

        Disambiguation rule:
          If the value is an integer (e.g. 1, 5, 20) OR a float that is an
          exact whole number (1.0, 5.0) AND the value is >= 1, treat it as
          a percentage and divide by 100.
          If it is a non-integer float < 1 (e.g. 0.01, 0.05), keep it as-is.
        """
        rate = float(self.hallucination_rate)
        # Whole-number values ≥ 1 are always percentages (1% … 100%)
        if rate >= 1.0 and rate == int(rate):
            rate = rate / 100.0
        # Non-integer floats > 1 are also percentages (e.g. 1.5 → 0.015)
        elif rate > 1.0:
            rate = rate / 100.0
        self.hallucination_rate = max(0.0, min(1.0, rate))
        self.retrieval_success_rate = max(0.0, min(1.0, float(self.retrieval_success_rate)))


@dataclass
class ReliabilityScore:
    """Breakdown of a scored agent's reliability."""
    agent_id: str
    agent_type: str
    overall_score: float

    # Core sub-scores (0–100)
    success_rate_score: float
    latency_score: float
    error_rate_score: float
    tool_stability_score: float

    # Quality sub-scores (0–100)
    hallucination_score: float      # higher = less hallucination = better
    retrieval_score: float          # based on retrieval_success_rate
    grounding_score: float          # based on grounded_responses ratio

    grade: str
    interpretation: str
    key_issues: list[str]
    raw_metrics: dict


# ------------------------------------------------------------------
# Individual Scoring Functions
# ------------------------------------------------------------------

def _score_success_rate(total: int, successful: int) -> float:
    """0.0–1.0. 100% success → 1.0. Below 90% curves down sharply."""
    if total == 0:
        return 1.0
    rate = successful / total
    if rate >= 0.99:
        return 1.0
    elif rate >= 0.95:
        return 0.85 + (rate - 0.95) * 3.0      # 0.85–1.0
    elif rate >= 0.90:
        return 0.65 + (rate - 0.90) * 4.0      # 0.65–0.85
    elif rate >= 0.80:
        return 0.40 + (rate - 0.80) * 2.5      # 0.40–0.65
    else:
        return max(0.0, rate * 0.5)


def _score_latency(p99_ms: float) -> float:
    """0.0–1.0. Based on P99 latency thresholds."""
    if p99_ms <= 1000:
        return 1.0
    elif p99_ms <= 2000:
        return 0.90 - (p99_ms - 1000) / 10000
    elif p99_ms <= 5000:
        return 0.80 - (p99_ms - 2000) / 10000
    elif p99_ms <= 10000:
        return 0.50 - (p99_ms - 5000) / 25000
    else:
        return max(0.0, 0.30 - (p99_ms - 10000) / 50000)


def _score_error_rate(total: int, errors: int) -> float:
    """0.0–1.0. Any error rate > 10% is disqualifying."""
    if total == 0:
        return 1.0
    rate = errors / total
    if rate == 0:
        return 1.0
    elif rate <= 0.01:
        return 0.95
    elif rate <= 0.05:
        return 0.85 - (rate - 0.01) * 5.0
    elif rate <= 0.10:
        return 0.65 - (rate - 0.05) * 4.0
    else:
        return max(0.0, 0.45 - rate * 2.0)


def _score_tool_stability(total_calls: int, failed_calls: int) -> float:
    """0.0–1.0. Tool stability directly affects agent quality."""
    if total_calls == 0:
        return 1.0
    fail_rate = failed_calls / total_calls
    if fail_rate == 0:
        return 1.0
    elif fail_rate <= 0.02:
        return 0.92
    elif fail_rate <= 0.05:
        return 0.78
    elif fail_rate <= 0.10:
        return 0.55
    else:
        return max(0.0, 0.55 - fail_rate * 3.0)


def _score_hallucination(hallucination_rate: float) -> float:
    """
    0.0–1.0.  hallucination_rate is a fraction (0.0–1.0).
    0% hallucination → 1.0; >20% → ~0.0.
    """
    rate = hallucination_rate  # already normalised in __post_init__
    if rate == 0.0:
        return 1.0
    elif rate <= 0.01:
        return 0.95
    elif rate <= 0.03:
        return 0.85 - (rate - 0.01) * 5.0
    elif rate <= 0.10:
        return 0.75 - (rate - 0.03) * 4.0
    elif rate <= 0.20:
        return 0.47 - (rate - 0.10) * 3.0
    else:
        return max(0.0, 0.17 - rate)


def _score_retrieval(retrieval_success_rate: float) -> float:
    """
    0.0–1.0.  Direct mapping from retrieval_success_rate.
    Perfect retrieval → 1.0; < 70% → severe penalty.
    """
    r = retrieval_success_rate
    if r >= 0.99:
        return 1.0
    elif r >= 0.90:
        return 0.85 + (r - 0.90) * 1.5
    elif r >= 0.80:
        return 0.70 + (r - 0.80) * 1.5
    elif r >= 0.70:
        return 0.50 + (r - 0.70) * 2.0
    else:
        return max(0.0, r * 0.7)


def _score_grounding(
    grounded_responses: int,
    successful_requests: int,
    hallucination_rate: float,
) -> float:
    """
    0.0–1.0.
    Uses grounded_responses ratio when data is available;
    falls back to an inverse of hallucination_rate when not.
    """
    if successful_requests > 0 and grounded_responses > 0:
        grounding_ratio = min(1.0, grounded_responses / successful_requests)
        return grounding_ratio
    # Fallback: estimate grounding from inverse hallucination
    return max(0.0, 1.0 - hallucination_rate * 2.0)


def _determine_grade(score: float) -> tuple[str, str]:
    if score >= 95:
        return "A+", "Excellent — production ready, no action needed"
    elif score >= 90:
        return "A",  "Very Good — monitor for drift"
    elif score >= 80:
        return "B",  "Good — minor optimizations recommended"
    elif score >= 70:
        return "C",  "Fair — reliability issues detected, investigation needed"
    elif score >= 60:
        return "D",  "Poor — active reliability problems, remediation required"
    else:
        return "F",  "Critical — agent is unreliable, immediate action required"


def _identify_issues(metrics: AgentMetrics, scores: dict) -> list[str]:
    issues = []

    if scores["success_rate"] < 0.80:
        rate = metrics.successful_requests / max(metrics.total_requests, 1)
        issues.append(f"Low success rate: {rate:.1%} (target ≥ 95%)")

    if scores["latency"] < 0.70:
        issues.append(f"High P99 latency: {metrics.p99_latency_ms:.0f} ms (target ≤ 2000 ms)")

    if scores["error_rate"] < 0.75:
        err = metrics.failed_requests / max(metrics.total_requests, 1)
        issues.append(f"Elevated error rate: {err:.1%} (target ≤ 5%)")
        top_errors = sorted(
            metrics.error_types.items(), key=lambda x: x[1], reverse=True
        )[:2]
        for etype, count in top_errors:
            issues.append(f"  → {etype}: {count} occurrences")

    if scores["tool_stability"] < 0.75:
        fail_rate = metrics.failed_tool_calls / max(metrics.total_tool_calls, 1)
        issues.append(f"Tool instability: {fail_rate:.1%} tool call failure rate")

    if scores["hallucination"] < 0.80:
        issues.append(
            f"Hallucination risk: {metrics.hallucination_rate:.1%} rate "
            f"(target < 3%)"
        )

    if scores["retrieval"] < 0.75:
        issues.append(
            f"Poor retrieval quality: {metrics.retrieval_success_rate:.1%} "
            f"success rate (target ≥ 90%)"
        )

    if scores["grounding"] < 0.70:
        gr = (
            metrics.grounded_responses / max(metrics.successful_requests, 1)
            if metrics.grounded_responses > 0
            else None
        )
        msg = (
            f"Low grounding ratio: {gr:.1%}"
            if gr is not None
            else "Insufficient grounding data — enable grounding in your agent"
        )
        issues.append(msg)

    return issues or ["No significant issues detected"]


# ------------------------------------------------------------------
# Main Scoring Function
# ------------------------------------------------------------------

def calculate_reliability_score(metrics: AgentMetrics) -> ReliabilityScore:
    """Compute a full reliability score breakdown from AgentMetrics."""

    sub_scores = {
        "success_rate":    _score_success_rate(metrics.total_requests, metrics.successful_requests),
        "latency":         _score_latency(metrics.p99_latency_ms),
        "error_rate":      _score_error_rate(metrics.total_requests, metrics.failed_requests),
        "tool_stability":  _score_tool_stability(metrics.total_tool_calls, metrics.failed_tool_calls),
        "hallucination":   _score_hallucination(metrics.hallucination_rate),
        "retrieval":       _score_retrieval(metrics.retrieval_success_rate),
        "grounding":       _score_grounding(
                               metrics.grounded_responses,
                               metrics.successful_requests,
                               metrics.hallucination_rate,
                           ),
    }

    weighted = (
        0.30 * sub_scores["success_rate"]
      + 0.20 * sub_scores["latency"]
      + 0.20 * sub_scores["error_rate"]
      + 0.10 * sub_scores["tool_stability"]
      + 0.10 * sub_scores["hallucination"]
      + 0.05 * sub_scores["retrieval"]
      + 0.05 * sub_scores["grounding"]
    )
    overall = round(weighted * 100, 1)
    grade, interpretation = _determine_grade(overall)
    issues = _identify_issues(metrics, sub_scores)

    return ReliabilityScore(
        agent_id=metrics.agent_id,
        agent_type=metrics.agent_type,
        overall_score=overall,
        success_rate_score=round(sub_scores["success_rate"] * 100, 1),
        latency_score=round(sub_scores["latency"] * 100, 1),
        error_rate_score=round(sub_scores["error_rate"] * 100, 1),
        tool_stability_score=round(sub_scores["tool_stability"] * 100, 1),
        hallucination_score=round(sub_scores["hallucination"] * 100, 1),
        retrieval_score=round(sub_scores["retrieval"] * 100, 1),
        grounding_score=round(sub_scores["grounding"] * 100, 1),
        grade=grade,
        interpretation=interpretation,
        key_issues=issues,
        raw_metrics={
            "total_requests":        metrics.total_requests,
            "successful_requests":   metrics.successful_requests,
            "failed_requests":       metrics.failed_requests,
            "p50_latency_ms":        metrics.p50_latency_ms,
            "p95_latency_ms":        metrics.p95_latency_ms,
            "p99_latency_ms":        metrics.p99_latency_ms,
            "total_tool_calls":      metrics.total_tool_calls,
            "failed_tool_calls":     metrics.failed_tool_calls,
            "total_tokens":          metrics.total_tokens,
            "hallucination_rate":    metrics.hallucination_rate,
            "retrieval_success_rate": metrics.retrieval_success_rate,
            "grounded_responses":    metrics.grounded_responses,
        },
    )


def score_multiple_agents(metrics_list: list[AgentMetrics]) -> list[ReliabilityScore]:
    """Score a batch of agents and sort by overall score descending."""
    scores = [calculate_reliability_score(m) for m in metrics_list]
    return sorted(scores, key=lambda s: s.overall_score, reverse=True)
