"""
Layer 6 — Cloud Run Services
Recommendation API: Aggregates outputs from all Gemini agents into a
prioritized list of actionable recommendations for the dashboard.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(str, Enum):
    RELIABILITY = "reliability"
    COST = "cost"
    LATENCY = "latency"
    SAFETY = "safety"
    QUALITY = "quality"


@dataclass
class Recommendation:
    """A single actionable recommendation for an agent."""
    recommendation_id: str
    agent_id: str
    agent_type: str
    category: Category
    priority: Priority
    title: str
    problem: str
    solution: str
    expected_impact: str
    implementation_steps: list[str]
    estimated_effort: str  # "30 min", "2 hours", "1 day"
    estimated_impact_score: float  # 0–10
    source_agent: str  # which Gemini agent generated this
    grounding_sources: list[str] = field(default_factory=list)
    confidence: float = 0.85
    auto_fixable: bool = False


@dataclass
class RecommendationBundle:
    """All recommendations for one monitored agent."""
    agent_id: str
    agent_type: str
    reliability_score: float
    recommendations: list[Recommendation]
    top_priority: Priority
    total_estimated_savings_usd: float
    projected_reliability_improvement: float  # points
    generated_at: str


def build_recommendation(
    rec_id: str,
    agent_id: str,
    agent_type: str,
    category: Category,
    priority: Priority,
    title: str,
    problem: str,
    solution: str,
    expected_impact: str,
    steps: list[str],
    effort: str,
    impact_score: float,
    source_agent: str,
    grounding: list[str] = None,
    auto_fixable: bool = False,
) -> Recommendation:
    return Recommendation(
        recommendation_id=rec_id,
        agent_id=agent_id,
        agent_type=agent_type,
        category=category,
        priority=priority,
        title=title,
        problem=problem,
        solution=solution,
        expected_impact=expected_impact,
        implementation_steps=steps,
        estimated_effort=effort,
        estimated_impact_score=impact_score,
        source_agent=source_agent,
        grounding_sources=grounding or [],
        auto_fixable=auto_fixable,
    )


def prioritize_recommendations(
    recommendations: list[Recommendation],
) -> list[Recommendation]:
    """
    Sort recommendations by priority (critical first) then by impact score.
    """
    priority_order = {
        Priority.CRITICAL: 0,
        Priority.HIGH: 1,
        Priority.MEDIUM: 2,
        Priority.LOW: 3,
    }
    return sorted(
        recommendations,
        key=lambda r: (priority_order[r.priority], -r.estimated_impact_score),
    )


def deduplicate_recommendations(
    recommendations: list[Recommendation],
) -> list[Recommendation]:
    """Remove duplicate recommendations (same title and agent_id)."""
    seen = set()
    deduped = []
    for r in recommendations:
        key = (r.agent_id, r.title.lower())
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


def bundle_recommendations(
    agent_id: str,
    agent_type: str,
    reliability_score: float,
    all_recommendations: list[Recommendation],
    cost_savings_usd: float = 0.0,
    timestamp: str = "",
) -> RecommendationBundle:
    """
    Combine and prioritize all recommendations for a given agent.
    """
    deduped = deduplicate_recommendations(all_recommendations)
    prioritized = prioritize_recommendations(deduped)

    top_priority = Priority.LOW
    if prioritized:
        top_priority = prioritized[0].priority

    # Project reliability improvement from all HIGH/CRITICAL fixes
    improvement = sum(
        r.estimated_impact_score * 0.5
        for r in prioritized
        if r.priority in (Priority.CRITICAL, Priority.HIGH)
    )

    from datetime import datetime, timezone
    ts = timestamp or datetime.now(timezone.utc).isoformat()

    return RecommendationBundle(
        agent_id=agent_id,
        agent_type=agent_type,
        reliability_score=reliability_score,
        recommendations=prioritized,
        top_priority=top_priority,
        total_estimated_savings_usd=round(cost_savings_usd, 4),
        projected_reliability_improvement=round(min(improvement, 20.0), 1),
        generated_at=ts,
    )


def format_recommendations_for_api(bundle: RecommendationBundle) -> dict:
    """Serialize a RecommendationBundle for the REST API / dashboard."""
    return {
        "agent_id": bundle.agent_id,
        "agent_type": bundle.agent_type,
        "reliability_score": bundle.reliability_score,
        "top_priority": bundle.top_priority.value,
        "projected_improvement": bundle.projected_reliability_improvement,
        "estimated_savings_usd": bundle.total_estimated_savings_usd,
        "generated_at": bundle.generated_at,
        "recommendations": [
            {
                "id": r.recommendation_id,
                "category": r.category.value,
                "priority": r.priority.value,
                "title": r.title,
                "problem": r.problem,
                "solution": r.solution,
                "expected_impact": r.expected_impact,
                "steps": r.implementation_steps,
                "effort": r.estimated_effort,
                "impact_score": r.estimated_impact_score,
                "source_agent": r.source_agent,
                "grounding": r.grounding_sources,
                "confidence": r.confidence,
                "auto_fixable": r.auto_fixable,
            }
            for r in bundle.recommendations
        ],
    }
