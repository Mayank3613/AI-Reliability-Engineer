"""
Trace Collector — Layer 2.
Fetches and normalizes distributed traces from Dynatrace
into AIRE's internal TraceRecord format for agent consumption.
"""

import os
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from dynatrace_client import DynatraceClient

logger = logging.getLogger(__name__)


@dataclass
class SpanRecord:
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    service_name: str
    start_time_ms: int
    duration_ms: float
    status: str  # "ok" | "error"
    error_message: Optional[str] = None
    attributes: dict = field(default_factory=dict)


@dataclass
class TraceRecord:
    trace_id: str
    service_name: str
    root_operation: str
    start_time_ms: int
    total_duration_ms: float
    span_count: int
    error_count: int
    spans: list[SpanRecord] = field(default_factory=list)
    tags: dict = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.span_count == 0:
            return 1.0
        return (self.span_count - self.error_count) / self.span_count

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0


class TraceCollector:
    """
    Pulls raw traces from Dynatrace and normalizes them
    into TraceRecord objects for AIRE agent consumption.
    """

    def __init__(self, dt_client: DynatraceClient | None = None):
        self.client = dt_client or DynatraceClient()

    def _normalize_span(self, raw: dict) -> SpanRecord:
        attrs = raw.get("attributes", {})
        error = raw.get("error", False)
        return SpanRecord(
            span_id=raw.get("spanId", ""),
            parent_span_id=raw.get("parentSpanId"),
            operation_name=raw.get("name", "unknown"),
            service_name=attrs.get("service.name", raw.get("serviceName", "unknown")),
            start_time_ms=raw.get("startTime", 0),
            duration_ms=raw.get("duration", 0) / 1_000_000,  # ns → ms
            status="error" if error else "ok",
            error_message=attrs.get("error.message") if error else None,
            attributes={
                k: v for k, v in attrs.items()
                if k.startswith(("llm.", "rag.", "tool.", "aire.", "coding.", "enterprise."))
            },
        )

    def _normalize_trace(self, raw: dict) -> TraceRecord:
        spans = [self._normalize_span(s) for s in raw.get("spans", [])]
        root = spans[0] if spans else None
        errors = [s for s in spans if s.status == "error"]

        return TraceRecord(
            trace_id=raw.get("traceId", ""),
            service_name=root.service_name if root else "unknown",
            root_operation=root.operation_name if root else "unknown",
            start_time_ms=root.start_time_ms if root else 0,
            total_duration_ms=sum(s.duration_ms for s in spans),
            span_count=len(spans),
            error_count=len(errors),
            spans=spans,
            tags={
                "llm.model": next(
                    (s.attributes.get("llm.model") for s in spans if "llm.model" in s.attributes),
                    None,
                )
            },
        )

    def collect(
        self,
        service_names: list[str],
        hours: int = 1,
        limit: int = 100,
    ) -> list[TraceRecord]:
        """
        Collect and normalize traces for the given services.
        """
        records: list[TraceRecord] = []

        for svc in service_names:
            try:
                raw_traces = self.client.get_traces(svc, hours=hours, limit=limit)
                normalized = [self._normalize_trace(t) for t in raw_traces]
                records.extend(normalized)
                logger.info(
                    "Collected %d traces for '%s' (errors: %d)",
                    len(normalized),
                    svc,
                    sum(1 for t in normalized if t.has_errors),
                )
            except Exception as e:
                logger.error("Failed to collect traces for '%s': %s", svc, e)

        return records

    def get_error_traces(self, service_names: list[str], hours: int = 1) -> list[TraceRecord]:
        all_traces = self.collect(service_names, hours=hours)
        return [t for t in all_traces if t.has_errors]

    def get_summary(self, traces: list[TraceRecord]) -> dict:
        if not traces:
            return {}

        total = len(traces)
        errors = sum(1 for t in traces if t.has_errors)
        avg_duration = sum(t.total_duration_ms for t in traces) / total
        p95_duration = sorted(t.total_duration_ms for t in traces)[int(total * 0.95)] if total > 1 else avg_duration

        return {
            "total_traces": total,
            "error_traces": errors,
            "success_rate": round((total - errors) / total, 4),
            "avg_duration_ms": round(avg_duration, 1),
            "p95_duration_ms": round(p95_duration, 1),
            "services": list({t.service_name for t in traces}),
            "collected_at": datetime.utcnow().isoformat() + "Z",
        }


# ── Demo / standalone run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()

    collector = TraceCollector()
    services = [
        "customer-support-agent",
        "research-agent",
        "coding-agent",
        "enterprise-agent",
    ]
    traces = collector.collect(services, hours=1)
    summary = collector.get_summary(traces)
    print(json.dumps(summary, indent=2))