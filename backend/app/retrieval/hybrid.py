from __future__ import annotations

import os
import re
import struct
from dataclasses import asdict, dataclass
from typing import Any, Literal

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient, models

from app.ingestion.index_documents import (
    DEFAULT_COLLECTION,
    DEFAULT_DIMENSIONS,
    DEFAULT_MODEL,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
)
from app.retrieval.cache import RedisCache, normalize_cache_text
from app.retrieval.sparse import normalize_text, payload_search_text, sparse_vector


DISTINCTIVE_TECH_TERMS = {
    "باکت",
    "channels",
    "certbot",
    "daphne",
    "dockerfile",
    "getenv",
    "ioredis",
    "nginx",
    "object storage",
    "outdir",
    "rclone",
    "redis_uri",
    "vite",
    "websocket",
    "wp-config",
}
SPECIAL_TOKEN_RE = re.compile(r"[^\s`]+[_./:-][^\s`]+")
RETRIEVAL_POLICY_VERSION = "adaptive-v1"


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
            f"Content:\n{self.content}"
        )


@dataclass(slots=True)
class RetrievalResult:
    documents: list[RetrievedChunk]
    strategy: Literal["cache", "sparse", "hybrid"]
    cached_strategy: str | None = None
    retrieval_cache_hit: bool = False
    embedding_cache_hit: bool = False
    embedding_request_made: bool = False


class HybridRetriever:
    def __init__(self) -> None:
        api_key = os.getenv("AVALAI_API_KEY") or os.getenv("LLM_API_KEY")
        if not api_key:
            raise RuntimeError("Set AVALAI_API_KEY (or legacy LLM_API_KEY)")

        self.collection = os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION)
        self.model = os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)
        self.dimensions = int(
            os.getenv("EMBEDDING_DIMENSIONS", str(DEFAULT_DIMENSIONS))
        )
        self.index_version = os.getenv("RAG_INDEX_VERSION", "v1")
        self.sparse_first = os.getenv("RAG_SPARSE_FIRST", "true").lower() == "true"
        self.sparse_min_score = float(os.getenv("RAG_SPARSE_MIN_SCORE", "25"))
        self.embedding_cache_ttl = int(
            os.getenv("RAG_EMBEDDING_CACHE_TTL_SECONDS", "2592000")
        )
        self.retrieval_cache_ttl = int(
            os.getenv("RAG_RETRIEVAL_CACHE_TTL_SECONDS", "86400")
        )
        self.cache = RedisCache()
        self.embeddings = OpenAIEmbeddings(
            model=self.model,
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

    def _retrieval_key(self, query: str, limit: int, candidate_limit: int) -> str:
        return self.cache.key(
            "retrieval",
            self.index_version,
            RETRIEVAL_POLICY_VERSION,
            self.collection,
            self.model,
            self.dimensions,
            self.sparse_first,
            self.sparse_min_score,
            limit,
            candidate_limit,
            normalize_cache_text(query),
        )

    def _embedding_key(self, query: str) -> str:
        return self.cache.key(
            "embedding",
            self.model,
            self.dimensions,
            normalize_cache_text(query),
        )

    def _dense_embedding(self, query: str) -> tuple[list[float], bool, bool]:
        key = self._embedding_key(query)
        cached = self.cache.get_bytes(key)
        expected_bytes = self.dimensions * 4
        if cached is not None and len(cached) == expected_bytes:
            embedding = list(struct.unpack(f"<{self.dimensions}f", cached))
            return embedding, True, False

        embedding = self.embeddings.embed_query(query)
        if len(embedding) != self.dimensions:
            raise RuntimeError(
                f"Expected {self.dimensions} query dimensions, got {len(embedding)}"
            )
        packed = struct.pack(f"<{self.dimensions}f", *embedding)
        self.cache.set_bytes(key, packed, self.embedding_cache_ttl)
        return embedding, False, True

    @staticmethod
    def _distinctive_terms(query: str) -> set[str]:
        normalized = normalize_cache_text(query)
        terms = {term for term in DISTINCTIVE_TECH_TERMS if term in normalized}
        for token in SPECIAL_TOKEN_RE.findall(query.casefold()):
            cleaned = token.strip(".,!?()[]{}<>\"'")
            if len(cleaned) >= 4:
                terms.add(cleaned)
        return terms

    def _sparse_is_confident(self, query: str, points: list[Any]) -> bool:
        if not points or float(points[0].score) < self.sparse_min_score:
            return False
        terms = self._distinctive_terms(query)
        if not terms:
            return False
        top_payload = points[0].payload or {}
        top_text = normalize_text(payload_search_text(top_payload))
        return any(normalize_text(term) in top_text for term in terms)

    def _query_sparse(self, query: str, candidate_limit: int) -> list[Any]:
        response = self.qdrant.query_points(
            collection_name=self.collection,
            query=sparse_vector(query, is_query=True),
            using=SPARSE_VECTOR_NAME,
            limit=candidate_limit,
            with_payload=True,
            with_vectors=False,
        )
        return list(response.points)

    @staticmethod
    def _to_documents(points: list[Any], limit: int) -> list[RetrievedChunk]:
        results: list[RetrievedChunk] = []
        seen_hashes: set[str] = set()
        for point in points:
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

    def _cached_result(self, key: str) -> RetrievalResult | None:
        payload = self.cache.get_json(key)
        if not isinstance(payload, dict) or not isinstance(payload.get("documents"), list):
            return None
        try:
            documents = [RetrievedChunk(**item) for item in payload["documents"]]
        except (TypeError, KeyError):
            return None
        return RetrievalResult(
            documents=documents,
            strategy="cache",
            cached_strategy=str(payload.get("strategy") or "hybrid"),
            retrieval_cache_hit=True,
            embedding_cache_hit=bool(payload.get("embedding_cache_hit")),
            embedding_request_made=False,
        )

    def _cache_result(self, key: str, result: RetrievalResult) -> None:
        self.cache.set_json(
            key,
            {
                "strategy": result.strategy,
                "embedding_cache_hit": result.embedding_cache_hit,
                "documents": [asdict(document) for document in result.documents],
            },
            self.retrieval_cache_ttl,
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 6,
        candidate_limit: int = 20,
    ) -> RetrievalResult:
        key = self._retrieval_key(query, limit, candidate_limit)
        cached = self._cached_result(key)
        if cached is not None:
            return cached

        sparse_points = self._query_sparse(query, candidate_limit)
        if self.sparse_first and self._sparse_is_confident(query, sparse_points):
            result = RetrievalResult(
                documents=self._to_documents(sparse_points, limit),
                strategy="sparse",
            )
            self._cache_result(key, result)
            return result

        dense_query, embedding_cache_hit, embedding_request_made = self._dense_embedding(query)
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
        result = RetrievalResult(
            documents=self._to_documents(list(response.points), limit),
            strategy="hybrid",
            embedding_cache_hit=embedding_cache_hit,
            embedding_request_made=embedding_request_made,
        )
        self._cache_result(key, result)
        return result
