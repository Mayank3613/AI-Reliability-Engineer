"""
Metric Collector — Layer 2.
Fetches and structures key LLM metrics from Dynatrace
for consumption by AIRE analysis agents.
"""

import os
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from dynatrace_client import DynatraceClient

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    timestamp_ms: int
    value: float
    dimensions: dict


@dataclass
class MetricSeries:
    metric_name: str
    display_name: str
    unit: str
    dimensions: dict
    points: list[MetricPoint]

    @property
    def latest(self) -> Optional[float]:
        return self.points[-1].value if self.points else None

    @property
    def avg(self) -> Optional[float]:
        if not self.points:
            return None
        return sum(p.value for p in self.points) / len(self.points)

    @property
    def max(self) -> Optional[float]:
        return max(p.value for p in self.points) if self.points else None


@dataclass
class AgentMetricSnapshot:
    """Complete metric snapshot for one agent at a point in time."""
    agent_name: str
    timestamp: str
    total_tokens: float
    prompt_tokens: float
    completion_tokens: float
    llm_calls: int
    error_count: int
    p95_latency_ms: float
    avg_latency_ms: float
    error_rate: float  # 0–1
    cost_estimate_usd: float


# Cost per 1M tokens (approximate Gemini pricing)
COST_PER_1M_TOKENS = {
    "gemini-1.5-pro": {"input": 3.50, "output": 10.50},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.0-pro": {"input": 0.50, "output": 1.50},
    "default": {"input": 1.00, "output": 3.00},
}


def estimate_cost(prompt_tokens: float, completion_tokens: float, model: str) -> float:
    pricing = COST_PER_1M_TOKENS.get(model, COST_PER_1M_TOKENS["default"])
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)


class MetricCollector:
    """
    Queries Dynatrace metric API and structures results
    into normalized AgentMetricSnapshot objects.
    """

    METRIC_DEFINITIONS = {
        "token_total": ("llm.token.count:splitBy(aire.agent,llm.model):sum", "tokens", "Total tokens"),
        "latency_p95": ("llm.call.latency:splitBy(aire.agent):percentile(95)", "ms", "P95 latency"),
        "latency_avg": ("llm.call.latency:splitBy(aire.agent):avg", "ms", "Avg latency"),
        "error_count": ("llm.error.count:splitBy(aire.agent):sum", "count", "Error count"),
        "call_count": ("llm.call.count:splitBy(aire.agent):count", "count", "LLM call count"),
    }

    def __init__(self, dt_client: DynatraceClient | None = None):
        self.client = dt_client or DynatraceClient()

    def _parse_series(self, raw_result: dict, name: str, unit: str, display: str) -> list[MetricSeries]:
        series_list = []
        for resolution in raw_result.get("resolution", {}).get("results", []):
            dims = resolution.get("dimensionMap", {})
            points = [
                MetricPoint(
                    timestamp_ms=p[0],
                    value=p[1] if p[1] is not None else 0.0,
                    dimensions=dims,
                )
                for p in resolution.get("data", [])
                if len(p) == 2
            ]
            series_list.append(
                MetricSeries(
                    metric_name=name,
                    display_name=display,
                    unit=unit,
                    dimensions=dims,
                    points=points,
                )
            )
        return series_list

    def collect_all(self, hours: int = 1) -> dict[str, list[MetricSeries]]:
        """Fetch all AIRE metrics from Dynatrace."""
        results = {}
        for key, (selector, unit, display) in self.METRIC_DEFINITIONS.items():
            try:
                raw = self.client.get_metric(selector, hours=hours)
                results[key] = self._parse_series(raw, key, unit, display)
                logger.info("Collected metric '%s': %d series", key, len(results[key]))
            except Exception as e:
                logger.error("Failed to collect metric '%s': %s", key, e)
                results[key] = []
        return results

    def build_snapshots(self, hours: int = 1) -> list[AgentMetricSnapshot]:
        """Build per-agent metric snapshots from raw Dynatrace data."""
        all_metrics = self.collect_all(hours=hours)
        snapshots: dict[str, AgentMetricSnapshot] = {}

        # Aggregate by agent
        for series in all_metrics.get("token_total", []):
            agent = series.dimensions.get("aire.agent", "unknown")
            model = series.dimensions.get("llm.model", "default")
            tokens = series.latest or 0.0

            if agent not in snapshots:
                snapshots[agent] = AgentMetricSnapshot(
                    agent_name=agent,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    total_tokens=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    llm_calls=0,
                    error_count=0,
                    p95_latency_ms=0,
                    avg_latency_ms=0,
                    error_rate=0,
                    cost_estimate_usd=0,
                )
            snapshots[agent].total_tokens += tokens

        for series in all_metrics.get("latency_p95", []):
            agent = series.dimensions.get("aire.agent", "unknown")
            if agent in snapshots:
                snapshots[agent].p95_latency_ms = series.latest or 0.0

        for series in all_metrics.get("latency_avg", []):
            agent = series.dimensions.get("aire.agent", "unknown")
            if agent in snapshots:
                snapshots[agent].avg_latency_ms = series.latest or 0.0

        for series in all_metrics.get("error_count", []):
            agent = series.dimensions.get("aire.agent", "unknown")
            if agent in snapshots:
                snapshots[agent].error_count += int(series.latest or 0)

        for series in all_metrics.get("call_count", []):
            agent = series.dimensions.get("aire.agent", "unknown")
            if agent in snapshots:
                snapshots[agent].llm_calls += int(series.latest or 0)

        # Compute derived metrics
        for snap in snapshots.values():
            if snap.llm_calls > 0:
                snap.error_rate = round(snap.error_count / snap.llm_calls, 4)
            snap.cost_estimate_usd = estimate_cost(
                snap.total_tokens * 0.7,  # assume 70% prompt
                snap.total_tokens * 0.3,  # assume 30% completion
                "default",
            )

        result = list(snapshots.values())
        logger.info("Built %d agent metric snapshots", len(result))
        return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()

    collector = MetricCollector()
    snapshots = collector.build_snapshots(hours=1)
    for snap in snapshots:
        print(json.dumps(snap.__dict__, indent=2, default=str))