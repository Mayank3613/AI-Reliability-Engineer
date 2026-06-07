"""
Datastore Client — Layer 5.
Manages documents in Google Agent Builder Data Store (Vertex AI Search).
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from google.cloud import discoveryengine_v1 as discoveryengine
    DISCOVERY_ENGINE_AVAILABLE = True
except ImportError:
    DISCOVERY_ENGINE_AVAILABLE = False


class DatastoreClient:
    """Upload, list, and delete documents in Agent Search datastore."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str = "global",
        data_store_id: str | None = None,
    ):
        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID", "")
        self.location = location
        self.data_store_id = data_store_id or os.environ.get(
            "AGENT_SEARCH_DATASTORE_ID", "aire-knowledge-store"
        )
        self._parent = (
            f"projects/{self.project_id}/locations/{self.location}"
            f"/collections/default_collection/dataStores/{self.data_store_id}"
            f"/branches/default_branch"
        )
        self._client = None

    def _get_client(self):
        if self._client is None and DISCOVERY_ENGINE_AVAILABLE:
            self._client = discoveryengine.DocumentServiceClient()
        return self._client

    def upload_document(
        self,
        doc_id: str,
        title: str,
        chunks: list[dict],
        metadata: dict | None = None,
    ) -> bool:
        """Upload a document with chunks to Agent Search."""
        client = self._get_client()
        if not client:
            logger.warning("DatastoreClient: Discovery Engine unavailable — skipping upload")
            return False

        content = "\n\n".join([c.get("text", "") for c in chunks])

        struct_data = {
            "title": title,
            "content": content,
            "chunk_count": len(chunks),
            **(metadata or {}),
        }

        try:
            document = discoveryengine.Document(
                id=doc_id,
                struct_data=struct_data,
            )
            request = discoveryengine.ImportDocumentsRequest(
                parent=self._parent,
                inline_source=discoveryengine.ImportDocumentsRequest.InlineSource(
                    documents=[document]
                ),
                reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.FULL,
            )
            client.import_documents(request)
            logger.info("Uploaded document '%s' (%d chunks)", doc_id, len(chunks))
            return True
        except Exception as e:
            logger.error("Upload failed for '%s': %s", doc_id, e)
            return False

    def list_documents(self) -> list[str]:
        """Return list of document IDs in the datastore."""
        client = self._get_client()
        if not client:
            return []
        try:
            docs = client.list_documents(parent=self._parent)
            return [d.id for d in docs]
        except Exception as e:
            logger.error("List documents failed: %s", e)
            return []

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the datastore."""
        client = self._get_client()
        if not client:
            return False
        try:
            name = f"{self._parent}/documents/{doc_id}"
            client.delete_document(name=name)
            logger.info("Deleted document '%s'", doc_id)
            return True
        except Exception as e:
            logger.error("Delete failed for '%s': %s", doc_id, e)
            return False