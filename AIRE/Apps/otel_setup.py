"""
OpenTelemetry setup for AIRE demo agents.
Configures tracing, metrics, and logging export to Dynatrace via OTLP.
"""

import os
import logging
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

logger = logging.getLogger(__name__)


def setup_otel(service_name: str, service_version: str = "1.0.0") -> tuple:
    """
    Initialize OpenTelemetry with Dynatrace OTLP export.

    Returns:
        (tracer, meter) tuple for use in agent code.
    """
    dt_endpoint = os.environ.get("DT_OTLP_ENDPOINT")
    dt_api_token = os.environ.get("DT_API_TOKEN")

    if not dt_endpoint or not dt_api_token:
        raise EnvironmentError(
            "DT_OTLP_ENDPOINT and DT_API_TOKEN must be set. "
            "Copy .env.example to .env and fill in your Dynatrace credentials."
        )

    headers = {
        "Authorization": f"Api-Token {dt_api_token}",
        "Content-Type": "application/x-protobuf",
    }

    resource = Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: service_name,
            ResourceAttributes.SERVICE_VERSION: service_version,
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: os.environ.get(
                "ENVIRONMENT", "development"
            ),
            "aire.component": "demo-agent",
        }
    )

    # --- Tracing ---
    span_exporter = OTLPSpanExporter(
        endpoint=f"{dt_endpoint}/v1/traces",
        headers=headers,
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)
    tracer = trace.get_tracer(service_name)

    # --- Metrics ---
    metric_exporter = OTLPMetricExporter(
        endpoint=f"{dt_endpoint}/v1/metrics",
        headers=headers,
    )
    reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=10_000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter(service_name)

    logger.info("OTel initialized for service '%s' → %s", service_name, dt_endpoint)
    return tracer, meter


def record_llm_call(
    tracer,
    meter,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    success: bool = True,
    tool_name: str | None = None,
    error: str | None = None,
):
    """
    Emit a standardized LLM call span + metrics.
    Follows the AIRE telemetry schema consumed by Bindplane.
    """
    token_counter = meter.create_counter(
        "llm.token.count",
        description="Total tokens used by LLM calls",
        unit="tokens",
    )
    latency_histogram = meter.create_histogram(
        "llm.call.latency",
        description="Latency of LLM calls in milliseconds",
        unit="ms",
    )
    error_counter = meter.create_counter(
        "llm.error.count",
        description="Number of failed LLM calls",
        unit="1",
    )

    attrs = {
        "llm.model": model,
        "llm.success": str(success),
        "aire.agent": tracer.instrumentation_scope.name,
    }
    if tool_name:
        attrs["llm.tool_name"] = tool_name
    if error:
        attrs["llm.error"] = error

    with tracer.start_as_current_span("llm.call", attributes=attrs) as span:
        span.set_attribute("llm.prompt_tokens", prompt_tokens)
        span.set_attribute("llm.completion_tokens", completion_tokens)
        span.set_attribute("llm.total_tokens", prompt_tokens + completion_tokens)
        span.set_attribute("llm.latency_ms", latency_ms)
        if not success:
            span.set_attribute("error", True)
            span.set_attribute("error.message", error or "unknown")

    token_counter.add(
        prompt_tokens + completion_tokens,
        {**attrs, "token.type": "total"},
    )
    latency_histogram.record(latency_ms, attrs)
    if not success:
        error_counter.add(1, attrs)