"""
OTel Exporter — Layer 2.
Configures OpenTelemetry SDK to export spans, metrics, and logs
to Dynatrace via OTLP/HTTP. Shared setup for all AIRE services.
"""

import os
import logging
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.sdk.resources import Resource, OTELResourceDetector
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.semconv.resource import ResourceAttributes

logger = logging.getLogger(__name__)

_initialized = False


def get_dynatrace_headers() -> dict:
    token = os.environ.get("DT_API_TOKEN")
    if not token:
        raise EnvironmentError("DT_API_TOKEN not set")
    return {
        "Authorization": f"Api-Token {token}",
        "Content-Type": "application/x-protobuf",
    }


def build_resource(service_name: str, extra: dict | None = None) -> Resource:
    base = {
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.SERVICE_VERSION: os.environ.get("SERVICE_VERSION", "1.0.0"),
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: os.environ.get("ENVIRONMENT", "development"),
        "aire.version": "1.0.0",
    }
    if extra:
        base.update(extra)
    return Resource.create(base)


def configure_tracing(
    resource: Resource,
    endpoint: str,
    headers: dict,
    debug: bool = False,
) -> trace.Tracer:
    """Set up BatchSpanProcessor → Dynatrace OTLP trace endpoint."""
    exporters = [OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", headers=headers)]
    if debug:
        exporters.append(ConsoleSpanExporter())

    provider = TracerProvider(resource=resource)
    for exp in exporters:
        provider.add_span_processor(BatchSpanProcessor(exp))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(resource.attributes[ResourceAttributes.SERVICE_NAME])


def configure_metrics(
    resource: Resource,
    endpoint: str,
    headers: dict,
    export_interval_ms: int = 10_000,
    debug: bool = False,
) -> metrics.Meter:
    """Set up PeriodicExportingMetricReader → Dynatrace OTLP metrics endpoint."""
    exporters = [
        OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics", headers=headers)
    ]
    if debug:
        exporters.append(ConsoleMetricExporter())

    readers = [
        PeriodicExportingMetricReader(exp, export_interval_millis=export_interval_ms)
        for exp in exporters
    ]
    provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(provider)
    return metrics.get_meter(resource.attributes[ResourceAttributes.SERVICE_NAME])


def init_telemetry(
    service_name: str,
    extra_resource_attrs: dict | None = None,
    debug: bool = False,
) -> tuple:
    """
    One-call telemetry initialization for any AIRE service.
    Returns (tracer, meter).
    """
    global _initialized
    if _initialized:
        logger.warning("Telemetry already initialized — returning existing providers")
        return (
            trace.get_tracer(service_name),
            metrics.get_meter(service_name),
        )

    endpoint = os.environ.get("DT_OTLP_ENDPOINT", "").rstrip("/")
    if not endpoint:
        raise EnvironmentError("DT_OTLP_ENDPOINT not set")

    headers = get_dynatrace_headers()
    resource = build_resource(service_name, extra_resource_attrs)

    tracer = configure_tracing(resource, endpoint, headers, debug)
    meter = configure_metrics(resource, endpoint, headers, debug=debug)

    _initialized = True
    logger.info("Telemetry initialized: service=%s env=%s",
                service_name, os.environ.get("ENVIRONMENT", "development"))

    return tracer, meter


def shutdown():
    """Flush all pending spans and metrics before process exit."""
    tp = trace.get_tracer_provider()
    if hasattr(tp, "shutdown"):
        tp.shutdown()
        logger.info("TracerProvider shut down")

    mp = metrics.get_meter_provider()
    if hasattr(mp, "shutdown"):
        mp.shutdown()
        logger.info("MeterProvider shut down")