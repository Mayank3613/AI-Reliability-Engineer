"""
Routing Rules — Layer 3.
Determines where each telemetry event is routed after transformation.
High-severity events get priority routing and alerting.
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


class Destination(str, Enum):
    DYNATRACE = "dynatrace"
    GOOGLE_CLOUD_MONITORING = "google_cloud_monitoring"
    DEAD_LETTER = "dead_letter"
    ALERT_WEBHOOK = "alert_webhook"


class Priority(str, Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class RoutingDecision:
    destinations: list[Destination]
    priority: Priority
    reason: str
    send_alert: bool = False


# ── Routing Rules (evaluated in order — first match wins) ────────────────────

ROUTING_RULES: list[tuple[Callable[[dict], bool], RoutingDecision]] = [

    # Rule 1: LLM errors → Dynatrace + alert
    (
        lambda e: e.get("event_type") == "llm_error",
        RoutingDecision(
            destinations=[Destination.DYNATRACE, Destination.ALERT_WEBHOOK],
            priority=Priority.HIGH,
            reason="LLM error requires immediate attention",
            send_alert=True,
        ),
    ),

    # Rule 2: High-latency events (>5s) → priority routing
    (
        lambda e: float(e.get("llm.latency_ms", 0)) > 5000,
        RoutingDecision(
            destinations=[Destination.DYNATRACE, Destination.GOOGLE_CLOUD_MONITORING],
            priority=Priority.HIGH,
            reason="Latency spike detected (>5000ms)",
            send_alert=True,
        ),
    ),

    # Rule 3: High token events (>10k tokens) → cost tracking
    (
        lambda e: int(e.get("llm.total_tokens", 0)) > 10_000,
        RoutingDecision(
            destinations=[Destination.DYNATRACE, Destination.GOOGLE_CLOUD_MONITORING],
            priority=Priority.NORMAL,
            reason="High token usage — cost tracking route",
        ),
    ),

    # Rule 4: Tool call failures → Dynatrace priority
    (
        lambda e: e.get("event_type") == "tool_call" and not e.get("llm.success", True),
        RoutingDecision(
            destinations=[Destination.DYNATRACE],
            priority=Priority.HIGH,
            reason="Tool call failure",
            send_alert=False,
        ),
    ),

    # Rule 5: Invalid/malformed events → dead letter
    (
        lambda e: bool(e.get("_validation_errors") or e.get("_transform_error")),
        RoutingDecision(
            destinations=[Destination.DEAD_LETTER],
            priority=Priority.LOW,
            reason="Event failed validation",
        ),
    ),

    # Rule 6: Default — all valid events to Dynatrace
    (
        lambda e: True,
        RoutingDecision(
            destinations=[Destination.DYNATRACE],
            priority=Priority.NORMAL,
            reason="Default route",
        ),
    ),
]


def route_event(event: dict) -> RoutingDecision:
    """Apply routing rules to a single normalized event."""
    for condition, decision in ROUTING_RULES:
        try:
            if condition(event):
                logger.debug(
                    "Event %s → %s [%s] — %s",
                    event.get("span_id", "?"),
                    [d.value for d in decision.destinations],
                    decision.priority.value,
                    decision.reason,
                )
                return decision
        except Exception as e:
            logger.warning("Routing rule evaluation error: %s", e)
            continue

    # Fallback — should never reach here
    return RoutingDecision(
        destinations=[Destination.DYNATRACE],
        priority=Priority.LOW,
        reason="Fallback — no rule matched",
    )


def route_batch(events: list[dict]) -> dict[str, list[dict]]:
    """
    Route a batch of events.
    Returns dict of destination → list of events.
    """
    buckets: dict[str, list[dict]] = {d.value: [] for d in Destination}
    alert_events: list[dict] = []

    for event in events:
        decision = route_event(event)
        for dest in decision.destinations:
            buckets[dest.value].append({
                **event,
                "_routing": {
                    "priority": decision.priority.value,
                    "reason": decision.reason,
                    "destinations": [d.value for d in decision.destinations],
                },
            })
        if decision.send_alert:
            alert_events.append(event)

    # Log routing summary
    for dest, evts in buckets.items():
        if evts:
            logger.info("Routed %d events → %s", len(evts), dest)

    if alert_events:
        logger.warning("⚠️  %d events flagged for alerting", len(alert_events))

    return buckets


def get_routing_summary(buckets: dict[str, list[dict]]) -> dict:
    return {
        "total": sum(len(v) for v in buckets.values()),
        "by_destination": {k: len(v) for k, v in buckets.items() if v},
        "high_priority": sum(
            1 for events in buckets.values()
            for e in events
            if e.get("_routing", {}).get("priority") == "high"
        ),
        "alerts_triggered": len(buckets.get(Destination.ALERT_WEBHOOK.value, [])),
    }