"""
Layer 5 — Knowledge / RAG
Embeddings: Vertex AI text-embedding-004 wrapper for local similarity scoring.
"""

import os
import math
import numpy as np
from typing import Optional
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
REGION = os.environ.get("GCP_REGION", "us-central1")
EMBEDDING_MODEL_ID = os.environ.get("EMBEDDING_MODEL", "text-embedding-004")

_model: Optional[TextEmbeddingModel] = None


def _get_model() -> TextEmbeddingModel:
    global _model
    if _model is None:
        aiplatform.init(project=PROJECT_ID, location=REGION)
        _model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL_ID)
    return _model


def embed_text(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """
    Generate a dense embedding vector for a single text string.

    task_type options:
      RETRIEVAL_QUERY       — for user queries
      RETRIEVAL_DOCUMENT    — for documents being indexed
      SEMANTIC_SIMILARITY   — for pairwise similarity
      CLASSIFICATION        — for classification tasks
    """
    model = _get_model()
    text = text[:8000]  # token budget safety
    embeddings = model.get_embeddings(
        [text],
        auto_truncate=True,
        output_dimensionality=768,
        task_type=task_type,
    )
    return embeddings[0].values


def embed_batch(
    texts: list[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
    batch_size: int = 16,
) -> list[list[float]]:
    """
    Embed a list of texts in batches.
    Vertex AI allows up to 250 embeddings per request; we use 16 for safety.
    """
    model = _get_model()
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        chunk = [t[:8000] for t in texts[i : i + batch_size]]
        results = model.get_embeddings(
            chunk,
            auto_truncate=True,
            output_dimensionality=768,
            task_type=task_type,
        )
        all_embeddings.extend([r.values for r in results])
    return all_embeddings


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def top_k_similar(
    query: str,
    candidates: list[str],
    k: int = 5,
) -> list[dict]:
    """
    Given a query string and a list of candidate strings,
    return the top-k most similar candidates with scores.
    """
    query_emb = embed_text(query, task_type="RETRIEVAL_QUERY")
    candidate_embs = embed_batch(candidates, task_type="RETRIEVAL_DOCUMENT")

    scored = [
        {"text": c, "score": cosine_similarity(query_emb, e)}
        for c, e in zip(candidates, candidate_embs)
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]
