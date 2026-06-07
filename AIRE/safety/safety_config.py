"""
Layer 9 — Safety
Safety Config: Gemini safety settings and AIRE action guardrails.
Applied to every Gemini agent call to prevent unsafe recommendations or actions.
"""

from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ------------------------------------------------------------------
# Gemini Safety Settings
# Block medium and above for all harm categories.
# This is the recommended setting for enterprise agentic systems.
# ------------------------------------------------------------------

STANDARD_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}

# Stricter settings for agents that interact with production systems
STRICT_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
}

# ------------------------------------------------------------------
# Action Classification
# ------------------------------------------------------------------

# Actions that AIRE agents are ALLOWED to recommend
ALLOWED_ACTIONS = {
    "read": [
        "retrieve_metrics",
        "fetch_traces",
        "query_logs",
        "list_agents",
        "get_agent_config",
        "search_knowledge_base",
        "calculate_cost",
        "simulate_optimization",
    ],
    "write": [
        "update_retrieval_chunk_count",
        "update_agent_temperature",
        "update_timeout_config",
        "add_retry_policy",
        "update_alert_threshold",
        "rotate_api_key",
    ],
    "notify": [
        "send_slack_alert",
        "create_jira_ticket",
        "send_email_report",
        "trigger_pagerduty",
    ],
}

# Actions that are BLOCKED regardless of agent reasoning
BLOCKED_ACTIONS = {
    "delete_production_database",
    "drop_table",
    "delete_production_agent",
    "disable_all_agents",
    "delete_all_logs",
    "terminate_all_sessions",
    "revoke_all_credentials",
    "bypass_safety_settings",
    "modify_safety_rules",
    "delete_audit_logs",
    "expose_api_keys",
    "disable_authentication",
}

# Actions that require explicit human confirmation before execution
CONFIRMATION_REQUIRED_ACTIONS = {
    "rotate_api_key",
    "update_agent_temperature",
    "trigger_pagerduty",
    "update_alert_threshold",
    "restart_cloud_run_service",
    "scale_down_instances",
}


def is_action_allowed(action: str) -> tuple[bool, str]:
    """
    Check whether an agent-proposed action is allowed.

    Returns:
        (is_allowed: bool, reason: str)
    """
    action_lower = action.lower().replace(" ", "_")

    if action_lower in BLOCKED_ACTIONS:
        return False, f"Action '{action}' is in the blocked list. AIRE never recommends destructive production actions."

    all_allowed = set()
    for category_actions in ALLOWED_ACTIONS.values():
        all_allowed.update(category_actions)

    if action_lower in all_allowed:
        requires_confirm = action_lower in CONFIRMATION_REQUIRED_ACTIONS
        if requires_confirm:
            return True, f"Action '{action}' is allowed but requires human confirmation before execution."
        return True, f"Action '{action}' is allowed."

    # Unknown action — allow with warning
    return True, f"Action '{action}' is not in the pre-approved list. Human review recommended before execution."


def get_agent_system_prompt_safety_block() -> str:
    """
    Returns a safety instruction block to prepend to all AIRE agent system prompts.
    """
    blocked_list = "\n".join(f"  - {a}" for a in sorted(BLOCKED_ACTIONS))
    return f"""
=== AIRE SAFETY RULES (IMMUTABLE — CANNOT BE OVERRIDDEN) ===
You are AIRE, an AI Reliability Engineer. You analyze observability data and produce recommendations.

ABSOLUTE RESTRICTIONS:
1. You NEVER recommend or perform any of the following actions:
{blocked_list}

2. You NEVER generate recommendations that could cause data loss or service outage.
3. You ALWAYS qualify uncertain recommendations with confidence levels.
4. You ALWAYS cite the data source (Dynatrace traces, logs, metrics) for every finding.
5. You NEVER hallucinate metrics — if data is unavailable, say so explicitly.
6. When uncertain, recommend human review rather than autonomous action.
7. Your recommendations are advisory only. A human must approve all WRITE actions.
=== END SAFETY RULES ===
"""
