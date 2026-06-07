"""
Layer 7 — Security
Credentials: Centralised credential resolution.
Prefers Secret Manager in production; falls back to env vars for local dev.
"""

import os
from typing import Optional
from functools import lru_cache

_USE_SECRET_MANAGER = os.environ.get("USE_SECRET_MANAGER", "true").lower() == "true"


def _resolve(env_key: str, secret_id: Optional[str] = None) -> str:
    """
    Resolve a credential value.
    1. In production (USE_SECRET_MANAGER=true): fetch from Secret Manager
    2. In local dev: read from environment variable
    """
    if _USE_SECRET_MANAGER and secret_id:
        try:
            from security.secret_manager import get_secret
            return get_secret(secret_id)
        except Exception as e:
            print(f"[Credentials] Secret Manager failed for '{secret_id}': {e}. Falling back to env.")

    value = os.environ.get(env_key, "")
    if not value:
        raise EnvironmentError(
            f"[Credentials] Missing credential: env var '{env_key}' is not set "
            f"and secret '{secret_id}' could not be fetched."
        )
    return value


# ------------------------------------------------------------------
# Dynatrace
# ------------------------------------------------------------------

@lru_cache(maxsize=None)
def dynatrace_api_key() -> str:
    return _resolve("DYNATRACE_API_KEY", "aire-dynatrace-api-key")


@lru_cache(maxsize=None)
def dynatrace_environment_id() -> str:
    return _resolve("DYNATRACE_ENVIRONMENT_ID", "aire-dynatrace-environment-id")


@lru_cache(maxsize=None)
def dynatrace_base_url() -> str:
    env_id = dynatrace_environment_id()
    return f"https://{env_id}.live.dynatrace.com"


# ------------------------------------------------------------------
# Google Cloud / Vertex AI
# ------------------------------------------------------------------

@lru_cache(maxsize=None)
def gcp_project_id() -> str:
    return _resolve("GCP_PROJECT_ID", None)  # Always set as env var


@lru_cache(maxsize=None)
def gcp_region() -> str:
    return os.environ.get("GCP_REGION", "us-central1")


@lru_cache(maxsize=None)
def vertex_ai_location() -> str:
    return os.environ.get("VERTEX_AI_LOCATION", "us-central1")


# ------------------------------------------------------------------
# Bindplane
# ------------------------------------------------------------------

@lru_cache(maxsize=None)
def bindplane_api_key() -> str:
    return _resolve("BINDPLANE_API_KEY", "aire-bindplane-api-key")


@lru_cache(maxsize=None)
def bindplane_endpoint() -> str:
    return _resolve("BINDPLANE_ENDPOINT", None)


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

def verify_all_credentials() -> dict[str, bool]:
    """Verify all required credentials are available. Returns a status map."""
    checks = {
        "dynatrace_api_key": False,
        "dynatrace_environment_id": False,
        "gcp_project_id": False,
        "bindplane_api_key": False,
    }
    for name, fn in [
        ("dynatrace_api_key", dynatrace_api_key),
        ("dynatrace_environment_id", dynatrace_environment_id),
        ("gcp_project_id", gcp_project_id),
        ("bindplane_api_key", bindplane_api_key),
    ]:
        try:
            fn()
            checks[name] = True
        except Exception:
            checks[name] = False
    return checks
