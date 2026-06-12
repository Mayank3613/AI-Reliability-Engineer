"""
Transform Rules — Layer 3.
Python transforms run by Bindplane to normalize raw OTel events
into AIRE's standardized telemetry schema before routing to Dynatrace.
"""

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── AIRE Telemetry Schema ─────────────────────────────────────────────────────
# Every event processed by Bindplane will have these fields after normalization.

REQUIRED_FIELDS = {
    "event_type",       # llm_call | tool_call | llm_error | agent_start | agent_end
    "aire.agent",       # agent service name
    "llm.model",        # gemini-1.5-pro | gemini-1.5-flash | etc.
    "timestamp_ms",     # Unix ms
}

OPTIONAL_FIELDS = {
    "llm.prompt_tokens",
    "llm.completion_tokens",
    "llm.total_tokens",
    "llm.latency_ms",
    "llm.tool_name",
    "llm.success",
    "error.message",
    "rag.chunks_retrieved",
    "rag.avg_score",
    "aire.component",
}


def normalize_event_type(span: dict) -> str:
    """Derive standardized event_type from OTel span attributes."""
    attrs = span.get("attributes", {})

    if attrs.get("error") is True:
        return "llm_error"
    if attrs.get("llm.tool_name"):
        return "tool_call"
    if "llm.model" in attrs:
        return "llm_call"
    if span.get("name", "").startswith("agent."):
        return "agent_lifecycle"
    return "span"


def normalize_model_name(raw_model: str | None) -> str:
    """Standardize model name across different formats."""
    if not raw_model:
        return "unknown"

    model = raw_model.lower().strip()
    mappings = {
        "gemini-1.5-pro-latest": "gemini-1.5-pro",
        "gemini-1.5-pro-001": "gemini-1.5-pro",
        "gemini-1.5-flash-latest": "gemini-1.5-flash",
        "gemini-1.5-flash-001": "gemini-1.5-flash",
        "gemini-1.0-pro": "gemini-1.0-pro",
    }
    return mappings.get(model, model)


def redact_pii(text: str) -> str:
    """Remove PII from attribute values before storage in Dynatrace."""
    if not text:
        return text
    # Email
    text = re.sub(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "[EMAIL]", text)
    # Phone (US)
    text = re.sub(r"\b(\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE]", text)
    # SSN
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", text)
    # Credit card (basic)
    text = re.sub(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b", "[CC]", text)
    return text


def transform_span(raw_span: dict) -> dict:
    """
    Main transform: takes a raw OTel span and returns the AIRE-normalized version.
    Applied by Bindplane before forwarding to Dynatrace.
    """
    attrs = raw_span.get("attributes", {})

    normalized = {
        # Core identification
        "span_id": raw_span.get("spanId", ""),
        "trace_id": raw_span.get("traceId", ""),
        "parent_span_id": raw_span.get("parentSpanId"),

        # AIRE schema
        "event_type": normalize_event_type(raw_span),
        "aire.agent": attrs.get("aire.agent", attrs.get("service.name", "unknown")),
        "llm.model": normalize_model_name(attrs.get("llm.model")),
        "timestamp_ms": raw_span.get("startTime", 0) // 1_000_000,  # ns → ms

        # LLM metrics
        "llm.prompt_tokens": attrs.get("llm.prompt_tokens", 0),
        "llm.completion_tokens": attrs.get("llm.completion_tokens", 0),
        "llm.total_tokens": attrs.get("llm.total_tokens", 0),
        "llm.latency_ms": attrs.get("llm.latency_ms", raw_span.get("duration", 0) / 1_000_000),

        # Tool call info
        "llm.tool_name": attrs.get("llm.tool_name"),
        "llm.success": not attrs.get("error", False),

        # Error info
        "error.message": redact_pii(attrs.get("error.message", "")) or None,

        # RAG info
        "rag.chunks_retrieved": attrs.get("rag.chunks_retrieved"),
        "rag.avg_score": attrs.get("rag.avg_score"),

        # Operation info
        "operation.name": raw_span.get("name", "unknown"),
        "duration_ms": raw_span.get("duration", 0) / 1_000_000,
    }

    # Redact any free-text fields that might contain PII
    for key in ["ticket.text", "enterprise.query_preview", "research.topic"]:
        if key in attrs:
            normalized[key] = redact_pii(str(attrs[key]))

    # Remove None values
    return {k: v for k, v in normalized.items() if v is not None}


def transform_metric(raw_metric: dict) -> dict:
    """
    Normalize a metric data point from OTel format.
    Adds AIRE cost_tier label based on model name.
    """
    attrs = raw_metric.get("attributes", {})
    model = normalize_model_name(attrs.get("llm.model"))

    cost_tier = "unknown"
    if "flash" in model:
        cost_tier = "standard"
    elif "pro" in model:
        cost_tier = "premium"

    return {
        **raw_metric,
        "attributes": {
            **attrs,
            "llm.model": model,
            "cost_tier": cost_tier,
            "aire.pipeline_version": "1.0",
        },
    }


def validate_event(event: dict) -> tuple[bool, list[str]]:
    """
    Check that a normalized event meets the AIRE schema.
    Returns (is_valid, list_of_missing_fields).
    """
    missing = [f for f in REQUIRED_FIELDS if not event.get(f)]
    return len(missing) == 0, missing


def batch_transform_spans(raw_spans: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Transform a batch of spans.
    Returns (valid_events, invalid_events).
    """
    valid, invalid = [], []

    for span in raw_spans:
        try:
            transformed = transform_span(span)
            ok, missing = validate_event(transformed)
            if ok:
                valid.append(transformed)
            else:
                invalid.append({**transformed, "_validation_errors": missing})
                logger.warning("Span %s missing fields: %s", span.get("spanId"), missing)
        except Exception as e:
            invalid.append({**span, "_transform_error": str(e)})
            logger.error("Transform error for span %s: %s", span.get("spanId"), e)

    logger.info(
        "Batch transform: %d valid, %d invalid (total: %d)",
        len(valid), len(invalid), len(raw_spans)
    )
    return valid, invalid