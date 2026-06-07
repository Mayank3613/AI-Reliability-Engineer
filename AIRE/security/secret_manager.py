"""
Layer 7 — Security
Secret Manager: Fetches credentials from Google Cloud Secret Manager.
All API keys and tokens must be retrieved via this module — never hardcoded.
"""

import os
from functools import lru_cache
from typing import Optional

from google.cloud import secretmanager
from google.api_core.exceptions import NotFound, PermissionDenied

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")

_client: Optional[secretmanager.SecretManagerServiceClient] = None


def _get_client() -> secretmanager.SecretManagerServiceClient:
    global _client
    if _client is None:
        _client = secretmanager.SecretManagerServiceClient()
    return _client


def get_secret(secret_id: str, version: str = "latest") -> str:
    """
    Retrieve a secret value from Secret Manager.

    Args:
        secret_id: The secret name (e.g. "dynatrace-api-key")
        version: Secret version (default "latest")

    Returns:
        The secret value as a string.

    Raises:
        ValueError if the secret is not found or access is denied.
    """
    client = _get_client()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version}"

    try:
        response = client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode("utf-8").strip()
        return payload
    except NotFound:
        raise ValueError(f"[SecretManager] Secret '{secret_id}' not found in project '{PROJECT_ID}'")
    except PermissionDenied:
        raise ValueError(
            f"[SecretManager] Access denied for secret '{secret_id}'. "
            "Ensure the Cloud Run service account has 'Secret Manager Secret Accessor' role."
        )
    except Exception as e:
        raise ValueError(f"[SecretManager] Failed to access secret '{secret_id}': {e}")


def create_secret(secret_id: str, value: str, labels: dict = None) -> str:
    """
    Create a new secret in Secret Manager.
    Returns the resource name of the created secret version.
    """
    client = _get_client()
    parent = f"projects/{PROJECT_ID}"

    try:
        secret = client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {
                    "replication": {"automatic": {}},
                    "labels": labels or {},
                },
            }
        )
    except Exception:
        # Secret already exists — add a new version
        secret_name = f"projects/{PROJECT_ID}/secrets/{secret_id}"
        version = client.add_secret_version(
            request={
                "parent": secret_name,
                "payload": {"data": value.encode("utf-8")},
            }
        )
        print(f"[SecretManager] Added new version to existing secret: {version.name}")
        return version.name

    version = client.add_secret_version(
        request={
            "parent": secret.name,
            "payload": {"data": value.encode("utf-8")},
        }
    )
    print(f"[SecretManager] Created secret and version: {version.name}")
    return version.name


def rotate_secret(secret_id: str, new_value: str) -> str:
    """Add a new version to an existing secret (rotation)."""
    client = _get_client()
    secret_name = f"projects/{PROJECT_ID}/secrets/{secret_id}"
    version = client.add_secret_version(
        request={
            "parent": secret_name,
            "payload": {"data": new_value.encode("utf-8")},
        }
    )
    print(f"[SecretManager] Rotated secret '{secret_id}' → new version: {version.name}")
    return version.name


def list_secrets(filter_prefix: str = "aire-") -> list[str]:
    """List all secrets in the project matching a prefix."""
    client = _get_client()
    parent = f"projects/{PROJECT_ID}"
    secrets = []
    for secret in client.list_secrets(request={"parent": parent}):
        name = secret.name.split("/")[-1]
        if name.startswith(filter_prefix):
            secrets.append(name)
    return secrets


# ------------------------------------------------------------------
# Typed accessors (cached per process lifetime)
# ------------------------------------------------------------------

@lru_cache(maxsize=None)
def get_dynatrace_api_key() -> str:
    return get_secret("aire-dynatrace-api-key")


@lru_cache(maxsize=None)
def get_dynatrace_environment_id() -> str:
    return get_secret("aire-dynatrace-environment-id")


@lru_cache(maxsize=None)
def get_gemini_api_key() -> str:
    """Only needed for direct API access; usually use ADC in Cloud Run."""
    return get_secret("aire-gemini-api-key")


@lru_cache(maxsize=None)
def get_bindplane_api_key() -> str:
    return get_secret("aire-bindplane-api-key")
