"""
RAG Pipeline — Layer 5.
Orchestrates document ingestion and search against Google Agent Search (Vertex AI Search).
Grounds AIRE agent recommendations in real reliability playbooks and documentation.
"""

import os
import logging
from pathlib import Path
from typing import Optional

from datastore_client import DatastoreClient
from agent_search import AgentSearchClient
from document_loader import DocumentLoader
from embeddings import EmbeddingsClient

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Full RAG pipeline:
    1. Load docs from /knowledge/docs/
    2. Chunk and embed
    3. Upload to Agent Search datastore
    4. Retrieve relevant chunks at query time
    """

    def __init__(
        self,
        datastore_client: DatastoreClient | None = None,
        search_client: AgentSearchClient | None = None,
        embeddings_client: EmbeddingsClient | None = None,
    ):
        self.datastore = datastore_client or DatastoreClient()
        self.search = search_client or AgentSearchClient()
        self.embeddings = embeddings_client or EmbeddingsClient()
        self.loader = DocumentLoader()
        logger.info("RAGPipeline initialized")

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def ingest_directory(self, docs_dir: str | Path) -> dict:
        """
        Load all markdown docs from a directory and upload to Agent Search.
        Returns ingestion summary.
        """
        docs_path = Path(docs_dir)
        if not docs_path.exists():
            raise FileNotFoundError(f"Docs directory not found: {docs_path}")

        md_files = list(docs_path.glob("*.md"))
        logger.info("Ingesting %d documents from %s", len(md_files), docs_path)

        summary = {"ingested": 0, "failed": 0, "total_chunks": 0, "files": []}

        for md_file in md_files:
            try:
                result = self._ingest_file(md_file)
                summary["ingested"] += 1
                summary["total_chunks"] += result["chunks"]
                summary["files"].append({"file": md_file.name, "chunks": result["chunks"]})
                logger.info("  ✓ %s → %d chunks", md_file.name, result["chunks"])
            except Exception as e:
                summary["failed"] += 1
                summary["files"].append({"file": md_file.name, "error": str(e)})
                logger.error("  ✗ %s: %s", md_file.name, e)

        logger.info(
            "Ingestion complete: %d ingested, %d failed, %d total chunks",
            summary["ingested"], summary["failed"], summary["total_chunks"]
        )
        return summary

    def _ingest_file(self, file_path: Path) -> dict:
        """Ingest a single markdown file."""
        # Load and chunk
        chunks = self.loader.load_and_chunk(file_path)
        logger.debug("  Loaded %d chunks from %s", len(chunks), file_path.name)

        # Embed
        embedded = self.embeddings.embed_chunks(chunks)

        # Upload to datastore
        doc_id = file_path.stem
        self.datastore.upload_document(
            doc_id=doc_id,
            title=file_path.stem.replace("_", " ").title(),
            chunks=embedded,
            metadata={
                "source": str(file_path),
                "category": "reliability_knowledge",
            },
        )

        return {"chunks": len(chunks), "doc_id": doc_id}

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Search Agent Search for relevant documents.
        Returns list of {content, source, score} dicts.
        """
        try:
            results = self.search.search(query, top_k=top_k)
            logger.debug(
                "RAG search '%s…' → %d results", query[:50], len(results)
            )
            return results
        except Exception as e:
            logger.warning("RAG search failed for '%s': %s", query, e)
            return []

    def get_context(self, query: str, top_k: int = 3, max_chars: int = 3000) -> str:
        """
        Get formatted context string for injection into agent prompts.
        """
        results = self.search(query, top_k=top_k)
        if not results:
            return ""

        parts = []
        total_chars = 0
        for i, r in enumerate(results, 1):
            content = r.get("content", "")
            source = r.get("source", "unknown")
            score = r.get("score", 0)

            chunk = f"[Source {i}: {source} | Score: {score:.2f}]\n{content}"
            if total_chars + len(chunk) > max_chars:
                break
            parts.append(chunk)
            total_chars += len(chunk)

        return "\n\n---\n\n".join(parts)

    def get_reliability_context(self, issue_type: str) -> str:
        """Pre-built queries for common AIRE use cases."""
        queries = {
            "reliability": "AI agent reliability scoring success rate latency error handling",
            "root_cause": "root cause analysis LLM failures timeout retry backoff",
            "cost": "LLM cost optimization token reduction context window compression",
            "recommendations": "AI agent production best practices improvements",
        }
        query = queries.get(issue_type, issue_type)
        return self.get_context(query, top_k=3)

    # ── Management ────────────────────────────────────────────────────────────

    def list_documents(self) -> list[str]:
        return self.datastore.list_documents()

    def delete_document(self, doc_id: str) -> bool:
        return self.datastore.delete_document(doc_id)

    def rebuild_index(self, docs_dir: str | Path) -> dict:
        """Wipe and rebuild the entire datastore from scratch."""
        logger.warning("Rebuilding Agent Search index — deleting all existing documents")
        for doc_id in self.list_documents():
            self.delete_document(doc_id)
        return self.ingest_directory(docs_dir)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()

    pipeline = RAGPipeline()

    if len(sys.argv) > 1 and sys.argv[1] == "ingest":
        docs_dir = sys.argv[2] if len(sys.argv) > 2 else "./docs"
        summary = pipeline.ingest_directory(docs_dir)
        print("Ingestion summary:", summary)

    elif len(sys.argv) > 1 and sys.argv[1] == "search":
        query = " ".join(sys.argv[2:]) or "reliability best practices"
        context = pipeline.get_context(query)
        print("=== RAG Context ===")
        print(context or "(no results)")

    else:
        print("Usage:")
        print("  python rag_pipeline.py ingest [./docs]")
        print("  python rag_pipeline.py search <query>")