"""
Dynatrace Client — Layer 2.
Wrapper around Dynatrace REST API v2 for querying ingested telemetry.
Used by AIRE agents to pull trace/metric/log data for analysis.
"""

import os
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class DynatraceClient:
    """
    Thin wrapper around the Dynatrace API v2.
    All methods return raw JSON for downstream agent consumption.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        api_token: str | None = None,
    ):
        self.endpoint = (endpoint or os.environ["DT_ENDPOINT"]).rstrip("/")
        self.api_token = api_token or os.environ["DT_API_TOKEN"]
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Api-Token {self.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json; charset=utf-8",
            }
        )
        logger.info("DynatraceClient initialized → %s", self.endpoint)

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.endpoint}/api/v2/{path.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.endpoint}/api/v2/{path.lstrip('/')}"
        resp = self.session.post(url, json=body, timeout=60)
        resp.raise_for_status()
        return resp.json()

    # ── Traces ────────────────────────────────────────────────────────────────

    def get_traces(
        self,
        service_name: str,
        hours: int = 1,
        limit: int = 100,
    ) -> list[dict]:
        """Fetch distributed traces for a given service name."""
        now = datetime.utcnow()
        from_time = (now - timedelta(hours=hours)).isoformat() + "Z"
        to_time = now.isoformat() + "Z"

        result = self._post(
            "traces/",
            {
                "query": f'service.name="{service_name}"',
                "startTime": from_time,
                "endTime": to_time,
                "pageSize": limit,
            },
        )
        traces = result.get("traces", [])
        logger.info("Fetched %d traces for '%s'", len(traces), service_name)
        return traces

    def get_span_errors(self, service_name: str, hours: int = 1) -> list[dict]:
        """Fetch error spans with error details."""
        result = self._post(
            "traces/",
            {
                "query": f'service.name="{service_name}" AND error=true',
                "startTime": (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z",
                "endTime": datetime.utcnow().isoformat() + "Z",
                "pageSize": 200,
            },
        )
        return result.get("traces", [])

    # ── Metrics ───────────────────────────────────────────────────────────────

    def get_metric(
        self,
        metric_selector: str,
        hours: int = 1,
        resolution: str = "1m",
    ) -> dict:
        """
        Query a metric by selector.
        Examples:
          metric_selector = "llm.token.count:splitBy(llm.model):sum"
          metric_selector = "llm.call.latency:splitBy(aire.agent):percentile(95)"
        """
        now = int(datetime.utcnow().timestamp() * 1000)
        from_ms = now - hours * 3_600_000

        return self._get(
            "metrics/query",
            {
                "metricSelector": metric_selector,
                "from": from_ms,
                "to": now,
                "resolution": resolution,
            },
        )

    def get_token_usage(self, hours: int = 1) -> dict:
        """Convenience: total token usage across all agents."""
        return self.get_metric(
            "llm.token.count:splitBy(aire.agent,llm.model):sum",
            hours=hours,
        )

    def get_latency_p95(self, hours: int = 1) -> dict:
        """Convenience: p95 latency per agent."""
        return self.get_metric(
            "llm.call.latency:splitBy(aire.agent):percentile(95)",
            hours=hours,
        )

    def get_error_rate(self, hours: int = 1) -> dict:
        """Convenience: error rate per agent."""
        return self.get_metric(
            "llm.error.count:splitBy(aire.agent):sum",
            hours=hours,
        )

    # ── Logs ──────────────────────────────────────────────────────────────────

    def get_logs(
        self,
        query: str = "",
        hours: int = 1,
        limit: int = 500,
    ) -> list[dict]:
        """Fetch log records matching a DQL query string."""
        now = datetime.utcnow()
        result = self._post(
            "logs/search",
            {
                "query": query,
                "from": (now - timedelta(hours=hours)).isoformat() + "Z",
                "to": now.isoformat() + "Z",
                "limit": limit,
            },
        )
        records = result.get("results", [])
        logger.info("Fetched %d log records", len(records))
        return records

    # ── Problems / Alerts ─────────────────────────────────────────────────────

    def get_open_problems(self, tag: str | None = None) -> list[dict]:
        """Fetch open Davis AI-detected problems."""
        params = {"problemSelector": "status(OPEN)"}
        if tag:
            params["problemSelector"] += f',tag("{tag}")'
        result = self._get("problems", params)
        return result.get("problems", [])

    # ── Health check ──────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        try:
            result = self._get("metrics/descriptors", {"pageSize": 1})
            logger.info("Dynatrace API health: OK")
            return True
        except Exception as e:
            logger.error("Dynatrace API health check failed: %s", e)
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()
    client = DynatraceClient()
    ok = client.health_check()
    print("Health OK:", ok)