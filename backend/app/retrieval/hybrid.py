from __future__ import annotations

import os
from dataclasses import dataclass

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient, models

from app.ingestion.index_documents import (
    DEFAULT_COLLECTION,
    DEFAULT_DIMENSIONS,
    DEFAULT_MODEL,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
)
from app.retrieval.sparse import sparse_vector


@dataclass(slots=True)
class RetrievedChunk:
    point_id: str
    score: float
    source_path: str
    source_url: str
    document_title: str
    heading_path: list[str]
    content: str
    content_hash: str

    def context(self, index: int) -> str:
        heading = " > ".join(self.heading_path)
        return (
            f"[Source {index}]\n"
            f"Title: {self.document_title}\n"
            f"Section: {heading}\n"
            f"Path: {self.source_path}\n"
            f"URL: {self.source_url}\n"
            f"Content:\n{self.content}"
        )


class HybridRetriever:
    def __init__(self) -> None:
        api_key = os.getenv("AVALAI_API_KEY") or os.getenv("LLM_API_KEY")
        if not api_key:
            raise RuntimeError("Set AVALAI_API_KEY (or legacy LLM_API_KEY)")

        self.collection = os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION)
        self.dimensions = int(
            os.getenv("EMBEDDING_DIMENSIONS", str(DEFAULT_DIMENSIONS))
        )
        self.embeddings = OpenAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL),
            dimensions=self.dimensions,
            api_key=api_key,
            base_url=os.getenv("AVALAI_BASE_URL", "https://api.avalai.ir/v1"),
            request_timeout=float(os.getenv("AVALAI_EMBEDDING_TIMEOUT", "60")),
            max_retries=1,
            check_embedding_ctx_length=False,
        )
        self.qdrant = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            timeout=30,
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 8,
        candidate_limit: int = 20,
    ) -> list[RetrievedChunk]:
        dense_query = self.embeddings.embed_query(query)
        if len(dense_query) != self.dimensions:
            raise RuntimeError(
                f"Expected {self.dimensions} query dimensions, got {len(dense_query)}"
            )

        response = self.qdrant.query_points(
            collection_name=self.collection,
            prefetch=[
                models.Prefetch(
                    query=dense_query,
                    using=DENSE_VECTOR_NAME,
                    limit=candidate_limit,
                ),
                models.Prefetch(
                    query=sparse_vector(query, is_query=True),
                    using=SPARSE_VECTOR_NAME,
                    limit=candidate_limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=candidate_limit,
            with_payload=True,
            with_vectors=False,
        )

        results: list[RetrievedChunk] = []
        seen_hashes: set[str] = set()
        for point in response.points:
            payload = point.payload or {}
            content = str(payload.get("content") or "").strip()
            content_hash = str(payload.get("content_hash") or point.id)
            if not content or content_hash in seen_hashes:
                continue
            if int(payload.get("token_count") or 0) < 30 and content.count("](") > 0:
                continue
            seen_hashes.add(content_hash)
            results.append(
                RetrievedChunk(
                    point_id=str(point.id),
                    score=float(point.score),
                    source_path=str(payload.get("source_path") or ""),
                    source_url=str(payload.get("source_url") or ""),
                    document_title=str(payload.get("document_title") or ""),
                    heading_path=[str(item) for item in payload.get("heading_path") or []],
                    content=content,
                    content_hash=content_hash,
                )
            )
            if len(results) == limit:
                break
        return results
