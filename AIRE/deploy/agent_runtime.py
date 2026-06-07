"""
Layer 8 — Deployment
Agent Runtime: Manages the lifecycle of Gemini agents deployed via
Vertex AI Agent Runtime. Provides start, stop, health, and invocation APIs.
"""

import os
import json
from typing import Optional, Any
from dataclasses import dataclass
import google.auth
import google.auth.transport.requests
import requests

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
REGION = os.environ.get("GCP_REGION", "us-central1")
AGENT_RUNTIME_BASE = f"https://{REGION}-aiplatform.googleapis.com/v1beta1"


@dataclass
class AgentRuntimeConfig:
    display_name: str
    description: str
    agent_framework: str = "custom"  # "custom", "langchain", "langgraph"
    runtime_version: str = "python311"
    memory_mb: int = 512
    timeout_seconds: int = 300
    max_instances: int = 5


@dataclass
class DeployedAgent:
    agent_id: str
    display_name: str
    resource_name: str
    state: str
    endpoint_uri: str
    create_time: str


def _get_auth_headers() -> dict:
    """Get OAuth2 authorization headers for Vertex AI API calls."""
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_request = google.auth.transport.requests.Request()
    creds.refresh(auth_request)
    return {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }


def create_agent_runtime(config: AgentRuntimeConfig) -> str:
    """
    Register a new agent runtime with Vertex AI.
    Returns the resource name of the created runtime.
    """
    parent = f"projects/{PROJECT_ID}/locations/{REGION}"
    url = f"{AGENT_RUNTIME_BASE}/{parent}/agentRuntimes"

    body = {
        "displayName": config.display_name,
        "description": config.description,
        "spec": {
            "agentFramework": config.agent_framework,
            "runtimeVersion": config.runtime_version,
            "resourceSpec": {
                "memoryMb": config.memory_mb,
            },
        },
        "networkSpec": {
            "enableInternetAccess": True,
        },
    }

    response = requests.post(url, headers=_get_auth_headers(), json=body)
    response.raise_for_status()
    result = response.json()
    print(f"[AgentRuntime] Created: {result.get('name')}")
    return result.get("name", "")


def list_agent_runtimes() -> list[dict]:
    """List all deployed agent runtimes in the project."""
    parent = f"projects/{PROJECT_ID}/locations/{REGION}"
    url = f"{AGENT_RUNTIME_BASE}/{parent}/agentRuntimes"

    response = requests.get(url, headers=_get_auth_headers())
    response.raise_for_status()
    return response.json().get("agentRuntimes", [])


def invoke_agent_runtime(
    runtime_name: str,
    session_id: str,
    user_message: str,
    context: Optional[dict] = None,
) -> dict:
    """
    Invoke a deployed agent runtime with a user message.

    Args:
        runtime_name: Full resource name of the agent runtime
        session_id: Unique session identifier
        user_message: The user input to send to the agent
        context: Optional additional context (telemetry data, agent metrics)

    Returns:
        Agent response dict with text + metadata
    """
    url = f"{AGENT_RUNTIME_BASE}/{runtime_name}:query"

    body = {
        "sessionId": session_id,
        "query": {
            "text": user_message,
        },
    }
    if context:
        body["query"]["structuredData"] = context

    response = requests.post(url, headers=_get_auth_headers(), json=body, timeout=300)
    response.raise_for_status()
    return response.json()


def delete_agent_runtime(runtime_name: str) -> None:
    """Delete a deployed agent runtime."""
    url = f"{AGENT_RUNTIME_BASE}/{runtime_name}"
    response = requests.delete(url, headers=_get_auth_headers())
    response.raise_for_status()
    print(f"[AgentRuntime] Deleted: {runtime_name}")


def get_runtime_health(runtime_name: str) -> dict:
    """Get the current state and health of a runtime."""
    url = f"{AGENT_RUNTIME_BASE}/{runtime_name}"
    response = requests.get(url, headers=_get_auth_headers())
    response.raise_for_status()
    data = response.json()
    return {
        "name": data.get("name"),
        "state": data.get("state", "UNKNOWN"),
        "create_time": data.get("createTime"),
        "update_time": data.get("updateTime"),
    }


# ------------------------------------------------------------------
# AIRE-specific runtime configs
# ------------------------------------------------------------------

AIRE_RUNTIME_CONFIGS = {
    "reliability": AgentRuntimeConfig(
        display_name="AIRE Reliability Analysis Agent",
        description="Analyzes agent telemetry and computes reliability scores",
        memory_mb=512,
        timeout_seconds=120,
    ),
    "root_cause": AgentRuntimeConfig(
        display_name="AIRE Root Cause Agent",
        description="Identifies root causes of agent failures from traces and logs",
        memory_mb=1024,
        timeout_seconds=180,
    ),
    "cost": AgentRuntimeConfig(
        display_name="AIRE Cost Optimization Agent",
        description="Analyzes token usage patterns and generates cost savings recommendations",
        memory_mb=512,
        timeout_seconds=120,
    ),
    "recommendation": AgentRuntimeConfig(
        display_name="AIRE Recommendation Agent",
        description="Aggregates all agent outputs into prioritized action recommendations",
        memory_mb=512,
        timeout_seconds=180,
    ),
}
