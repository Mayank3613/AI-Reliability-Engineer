"""
Agent Search Client — Layer 5.
Wraps Google Cloud Vertex AI Agent Builder / Discovery Engine API
for document retrieval powering AIRE's RAG recommendations.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from google.cloud import discoveryengine_v1 as discoveryengine
    from google.api_core.client_options import ClientOptions
    DISCOVERY_ENGINE_AVAILABLE = True
except ImportError:
    DISCOVERY_ENGINE_AVAILABLE = False
    logger.warning("google-cloud-discoveryengine not installed — using mock search")


class AgentSearchClient:
    """
    Client for Google Agent Search (Vertex AI Search).
    Falls back to keyword matching when Discovery Engine isn't configured.
    """

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
        self._client = None
        self._serving_config = (
            f"projects/{self.project_id}/locations/{self.location}"
            f"/collections/default_collection/dataStores/{self.data_store_id}"
            f"/servingConfigs/default_search"
        )
        logger.info(
            "AgentSearchClient: project=%s datastore=%s",
            self.project_id, self.data_store_id
        )

    def _get_client(self):
        if self._client is None and DISCOVERY_ENGINE_AVAILABLE:
            opts = None
            if self.location != "global":
                opts = ClientOptions(
                    api_endpoint=f"{self.location}-discoveryengine.googleapis.com"
                )
            self._client = discoveryengine.SearchServiceClient(client_options=opts)
        return self._client

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Search the Agent Search datastore for relevant documents.
        Returns normalized list of {content, source, score, title} dicts.
        """
        client = self._get_client()

        if client is None:
            logger.warning("Discovery Engine client unavailable — returning mock results")
            return self._mock_search(query, top_k)

        try:
            request = discoveryengine.SearchRequest(
                serving_config=self._serving_config,
                query=query,
                page_size=top_k,
                content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
                    snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                        return_snippet=True,
                        max_snippet_count=3,
                    ),
                    summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                        summary_result_count=top_k,
                        include_citations=True,
                    ),
                ),
            )

            response = client.search(request)
            results = []

            for result in response.results:
                doc = result.document
                snippets = [
                    s.snippet
                    for s in result.model_scores.get("snippets", [])
                    if hasattr(s, "snippet")
                ] or [""]

                results.append({
                    "id": doc.id,
                    "title": doc.derived_struct_data.get("title", doc.id),
                    "content": " ".join(snippets) or doc.derived_struct_data.get("snippet", ""),
                    "source": doc.derived_struct_data.get("source", "unknown"),
                    "score": getattr(result, "relevance_score", 0.5),
                })

            logger.info("Agent Search '%s…' → %d results", query[:40], len(results))
            return results

        except Exception as e:
            logger.error("Agent Search error: %s", e)
            return self._mock_search(query, top_k)

    def _mock_search(self, query: str, top_k: int) -> list[dict]:
        """
        Fallback keyword search over local docs.
        Used in development when Discovery Engine isn't configured.
        """
        from pathlib import Path

        docs_dir = Path(__file__).parent / "docs"
        if not docs_dir.exists():
            return []

        query_words = set(query.lower().split())
        scored = []

        for md_file in docs_dir.glob("*.md"):
            try:
                content = md_file.read_text()
                words = set(content.lower().split())
                score = len(query_words & words) / max(len(query_words), 1)
                if score > 0:
                    scored.append({
                        "id": md_file.stem,
                        "title": md_file.stem.replace("_", " ").title(),
                        "content": content[:1000],
                        "source": md_file.name,
                        "score": round(score, 3),
                    })
            except Exception:
                pass

        return sorted(scored, key=lambda x: x["score"], reverse=True)[:top_k]